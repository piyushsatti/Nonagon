from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.utils.log_stream import send_demo_log
from app.domain.models.CharacterModel import Character
from app.domain.models.EntityIDModel import CharacterID, UserID
from app.domain.models.UserModel import User
from app.infra.mongo.guild_adapter import upsert_character_sync
from app.bot.config import BOT_FLUSH_VIA_ADAPTER
from app.infra.serialization import to_bson


class CharacterCommandsCog(commands.Cog):
	"""Slash commands for player character management."""

	def __init__(self, bot: commands.Bot):
		self.bot = bot

	async def _ensure_guild_cache(self, guild: discord.Guild) -> None:
		if guild.id not in self.bot.guild_data:
			await self.bot.load_or_create_guild_cache(guild)

	async def _get_cached_user(self, member: discord.Member) -> User:
		await self._ensure_guild_cache(member.guild)
		guild_entry = self.bot.guild_data[member.guild.id]

		user = guild_entry["users"].get(member.id)
		if user is not None:
			return user

		listener: Optional[commands.Cog] = self.bot.get_cog("ListnerCog")
		if listener is None:
			raise RuntimeError("Listener cog not loaded; cannot resolve users.")

		ensure_method = getattr(listener, "_ensure_cached_user", None)
		if ensure_method is None:
			raise RuntimeError("Listener cog missing _ensure_cached_user helper.")

		user = await ensure_method(member)  # type: ignore[misc]
		return user

	def _next_character_id(self, guild_id: int) -> CharacterID:
		guild_entry = self.bot.guild_data[guild_id]
		db = guild_entry["db"]
		coll = db["characters"]
		while True:
			candidate = CharacterID.generate()
			exists = coll.count_documents(
				{"guild_id": guild_id, "character_id": str(candidate)}, limit=1
			)
			if not exists:
				return candidate

	def _persist_character(self, guild_id: int, character: Character) -> None:
		if BOT_FLUSH_VIA_ADAPTER:
			from app.bot.database import db_client
			upsert_character_sync(db_client, guild_id, character)
			return
		guild_entry = self.bot.guild_data[guild_id]
		db = guild_entry["db"]
		character.guild_id = guild_id
		doc = to_bson(character)
		doc["guild_id"] = guild_id
		doc["character_id"] = str(character.character_id)
		db["characters"].update_one(
			{"guild_id": guild_id, "character_id": str(character.character_id)},
			{"$set": doc},
			upsert=True,
		)

	@app_commands.command(name="character_add", description="Create a new character profile.")
	@app_commands.describe(
		name="Character name",
		ddb_link="D&D Beyond (or sheet) link",
		character_thread_link="Forum/thread link for the character",
		token_link="Token image link",
		art_link="Character art link",
		description="Short description",
		notes="Private notes",
		tags="Comma-separated tags",
	)
	async def character_add(
		self,
		interaction: discord.Interaction,
		name: str,
		ddb_link: str,
		character_thread_link: str,
		token_link: str,
		art_link: str,
		description: Optional[str] = None,
		notes: Optional[str] = None,
		tags: Optional[str] = None,
	) -> None:
		await interaction.response.defer(ephemeral=True)

		if interaction.guild is None:
			await interaction.followup.send(
				"This command can only be used inside a guild.", ephemeral=True
			)
			return

		member = interaction.user
		if not isinstance(member, discord.Member):
			await interaction.followup.send(
				"Only guild members can add characters.", ephemeral=True
			)
			return

		try:
			user = await self._get_cached_user(member)
		except RuntimeError as exc:
			logging.exception("Failed to resolve user for character creation: %s", exc)
			await interaction.followup.send(
				"Internal error resolving your profile; please try again later.",
				ephemeral=True,
			)
			return

		if not user.is_player:
			user.enable_player()

		char_id = self._next_character_id(interaction.guild.id)
		tag_list = (
			[t.strip() for t in tags.split(",") if t.strip()] if tags is not None else []
		)

		character = Character(
			character_id=str(char_id),
			owner_id=user.user_id,
			name=name,
			ddb_link=ddb_link,
			character_thread_link=character_thread_link,
			token_link=token_link,
			art_link=art_link,
			description=description,
			notes=notes,
			tags=tag_list,
			created_at=datetime.now(timezone.utc),
			guild_id=interaction.guild.id,
		)

		try:
			character.validate_character()
		except ValueError as exc:
			await interaction.followup.send(
				f"Character validation failed: {exc}", ephemeral=True
			)
			return

		if user.player is None:
			user.enable_player()
		if user.player is not None and char_id not in user.player.characters:
			user.player.characters.append(CharacterID.parse(str(char_id)))

		try:
			user.validate_user()
		except ValueError as exc:
			await interaction.followup.send(
				f"User validation failed after character creation: {exc}",
				ephemeral=True,
			)
			return

		self._persist_character(interaction.guild.id, character)
		await self.bot.dirty_data.put((interaction.guild.id, member.id))

		logging.info(
			"Character %s created by %s in guild %s",
			char_id,
			member.id,
			interaction.guild.id,
		)

		await send_demo_log(
			self.bot,
			interaction.guild,
			f"{member.mention} created character `{name}` ({char_id})",
		)

		await interaction.followup.send(
			f"Character `{name}` created with ID `{char_id}`.", ephemeral=True
		)

	@app_commands.command(name="character_list", description="List your characters.")
	async def character_list(self, interaction: discord.Interaction) -> None:
		if interaction.guild is None:
			await interaction.response.send_message(
				"This command can only be used inside a guild.", ephemeral=True
			)
			return

		member = interaction.user
		if not isinstance(member, discord.Member):
			await interaction.response.send_message(
				"Only guild members can list characters.", ephemeral=True
			)
			return

		await self._ensure_guild_cache(interaction.guild)
		guild_entry = self.bot.guild_data[interaction.guild.id]
		db = guild_entry["db"]

		owner_id = str(UserID.from_body(str(member.id)))
		cursor = db["characters"].find(
			{
				"guild_id": interaction.guild.id,
				"owner_id.value": owner_id,
			},
			{"_id": 0, "character_id": 1, "name": 1, "ddb_link": 1},
		)
		characters = list(cursor)

		if not characters:
			await interaction.response.send_message(
				"You do not have any characters yet. Use `/character_add` to create one!",
				ephemeral=True,
			)
			return

		embed = discord.Embed(
			title=f"{member.display_name}'s Characters",
			colour=discord.Color.green(),
		)
		for doc in characters:
			char_id = doc["character_id"]
			if isinstance(char_id, dict):
				label = char_id.get("value") or f"{char_id.get('prefix', 'CHAR')}{char_id.get('number', '')}"
			else:
				label = str(char_id)
			embed.add_field(
				name=f"{label} — {doc.get('name', 'Unnamed')}",
				value=doc.get("ddb_link", "No sheet link"),
				inline=False,
			)

		await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
	await bot.add_cog(CharacterCommandsCog(bot))
