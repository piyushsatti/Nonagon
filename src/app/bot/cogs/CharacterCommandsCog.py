from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.services import guild_settings_store
from app.bot.utils.log_stream import send_demo_log
from app.bot.cogs._staff_utils import is_allowed_staff
from app.domain.models.CharacterModel import Character, CharacterRole
from app.domain.models.EntityIDModel import CharacterID, UserID
from app.domain.models.UserModel import User
from app.infra.mongo.guild_adapter import upsert_character_sync
from app.bot.config import BOT_FLUSH_VIA_ADAPTER
from app.infra.serialization import from_bson, to_bson


class CharacterCommandsCog(commands.Cog):
	"""Slash commands for player character management."""

	character = app_commands.Group(
		name="character", description="Manage Nonagon character profiles."
	)

	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self._active_dm_sessions: set[int] = set()

	async def _fetch_character(
		self, guild: discord.Guild, raw_character_id: str
	) -> Optional[Character]:
		await self._ensure_guild_cache(guild)
		guild_entry = self.bot.guild_data[guild.id]
		db = guild_entry["db"]
		try:
			normalized = str(CharacterID.parse(raw_character_id))
		except Exception:
			normalized = raw_character_id.strip().upper()

		doc = db["characters"].find_one(
			{"guild_id": guild.id, "character_id": normalized}
		)
		if doc is None:
			doc = db["characters"].find_one(
				{"guild_id": guild.id, "character_id.value": normalized}
			)
		if doc is None:
			return None

		character = from_bson(Character, doc)
		character.guild_id = guild.id
		if isinstance(character.tags, list):
			character.tags = [str(tag) for tag in character.tags]
		else:
			character.tags = []
		if not isinstance(character.owner_id, UserID):
			try:
				character.owner_id = UserID.parse(str(character.owner_id))
			except Exception:
				pass
		if not character.status:
			character.status = CharacterRole.ACTIVE
		return character

	def _can_manage_character(
		self, member: discord.Member, character: Character
	) -> bool:
		try:
			owner_id = UserID.from_body(str(member.id))
		except Exception:
			owner_id = None
		if owner_id and character.owner_id == owner_id:
			return True
		return is_allowed_staff(self.bot, member)

	async def _update_character_announcement(
		self, guild: discord.Guild, character: Character
	) -> Optional[str]:
		channel_id = character.announcement_channel_id
		message_id = character.announcement_message_id
		if not channel_id or not message_id:
			return "No announcement message is stored for this character."

		channel: Optional[discord.abc.GuildChannel] = guild.get_channel(channel_id)
		if channel is None:
			try:
				channel = await guild.fetch_channel(channel_id)
			except (discord.HTTPException, discord.Forbidden, discord.NotFound):
				return "Unable to access the stored announcement channel."

		if not isinstance(channel, discord.TextChannel):
			return "Stored announcement channel is not a text channel."

		try:
			message = await channel.fetch_message(message_id)
		except discord.NotFound:
			return "Announcement message could not be found."
		except discord.Forbidden:
			return "I lack permission to edit the announcement message."
		except discord.HTTPException as exc:
			logging.exception(
				"Failed to fetch announcement message %s/%s: %s",
				channel_id,
				message_id,
				exc,
			)
			return "Failed to fetch the announcement message."

		embed = self._build_character_embed_from_model(character)
		try:
			await message.edit(embed=embed)
		except discord.HTTPException as exc:
			logging.exception("Failed to edit character announcement message: %s", exc)
			return "Failed to update the announcement message."

		note: Optional[str] = None
		if character.onboarding_thread_id:
			thread = guild.get_thread(character.onboarding_thread_id)
			if thread is None:
				candidate = self.bot.get_channel(character.onboarding_thread_id)
				if isinstance(candidate, discord.Thread):
					thread = candidate
			if thread is not None:
				desired_name = self._desired_thread_name(character)
				if thread.name != desired_name:
					try:
						await thread.edit(
							name=desired_name,
							reason="Character profile updated",
						)
					except discord.HTTPException as exc:
						logging.debug("Failed to rename character thread: %s", exc)
						note = (
							note or ""
						) + " Thread rename failed due to missing permissions."
			elif note is None:
				note = "The onboarding thread could not be found."

		return note

	async def _owned_character_docs(
		self, guild: discord.Guild, member: discord.Member
	) -> List[dict]:
		await self._ensure_guild_cache(guild)
		guild_entry = self.bot.guild_data[guild.id]
		db = guild_entry["db"]
		owner_id = str(UserID.from_body(str(member.id)))
		cursor = db["characters"].find(
			{
				"guild_id": guild.id,
				"owner_id.value": owner_id,
			},
			{
				"_id": 0,
				"character_id": 1,
				"name": 1,
				"ddb_link": 1,
				"status": 1,
				"announcement_channel_id": 1,
				"announcement_message_id": 1,
			},
		)
		return list(cursor)

	@staticmethod
	def _normalize_character_id(raw: object) -> str:
		if isinstance(raw, dict):
			value = raw.get("value")
			if value is not None:
				return str(value)
			prefix = raw.get("prefix", CharacterID.prefix)
			number = raw.get("number")
			if number is not None:
				return f"{prefix}{number}"
		return str(raw)

	async def _handle_status_change(
		self,
		interaction: discord.Interaction,
		character_id: str,
		target_status: CharacterRole,
		success_message: str,
		already_message: str,
	) -> None:
		if interaction.guild is None:
			await interaction.response.send_message(
				"This command can only be used inside a guild.", ephemeral=True
			)
			return

		member = interaction.user
		if not isinstance(member, discord.Member):
			await interaction.response.send_message(
				"Only guild members can manage characters.", ephemeral=True
			)
			return

		character = await self._fetch_character(interaction.guild, character_id)
		if character is None:
			await interaction.response.send_message(
				f"Character `{character_id}` was not found.", ephemeral=True
			)
			return

		if not self._can_manage_character(member, character):
			await interaction.response.send_message(
				"You do not have permission to modify this character.",
				ephemeral=True,
			)
			return

		if character.status is target_status:
			await interaction.response.send_message(
				already_message.format(name=character.name),
				ephemeral=True,
			)
			return

		if target_status is CharacterRole.INACTIVE:
			character.deactivate()
		else:
			character.activate()

		self._persist_character(interaction.guild.id, character)
		note = await self._update_character_announcement(interaction.guild, character)

		await send_demo_log(
			self.bot,
			interaction.guild,
			f"{member.mention} set character `{character.name}` ({character.character_id}) to {self._status_label(character.status)}.",
		)

		message = success_message.format(name=character.name)
		if note:
			message = f"{message}\n{note}"

		await interaction.response.send_message(message, ephemeral=True)

	@staticmethod
	def _status_label(status: CharacterRole) -> str:
		return "Active" if status is CharacterRole.ACTIVE else "Retired"

	def _build_character_embed(
		self,
		*,
		name: str,
		ddb_link: Optional[str],
		character_thread_link: Optional[str],
		token_link: Optional[str],
		art_link: Optional[str],
		description: Optional[str],
		tags: List[str],
		status: CharacterRole,
		updated_at: Optional[datetime] = None,
	) -> discord.Embed:
		colour = (
			discord.Color.blurple()
			if status is CharacterRole.ACTIVE
			else discord.Color.dark_grey()
		)
		embed = discord.Embed(
			title=name or "Unnamed Character",
			description=description or "No description provided.",
			colour=colour,
			timestamp=updated_at or datetime.now(timezone.utc),
		)
		embed.add_field(
			name="Sheet",
			value=ddb_link or "Not set",
			inline=False,
		)
		embed.add_field(
			name="Character Thread",
			value=character_thread_link or "Not set",
			inline=False,
		)
		embed.add_field(
			name="Token",
			value=token_link or "Not set",
			inline=False,
		)
		embed.add_field(
			name="Status",
			value=self._status_label(status),
			inline=False,
		)
		if tags:
			embed.add_field(
				name="Tags",
				value=", ".join(f"`{tag}`" for tag in tags),
				inline=False,
			)
		if art_link:
			embed.set_image(url=art_link)
		return embed

	def _build_character_embed_from_model(self, character: Character) -> discord.Embed:
		return self._build_character_embed(
			name=character.name,
			ddb_link=character.ddb_link,
			character_thread_link=character.character_thread_link,
			token_link=character.token_link,
			art_link=character.art_link,
			description=character.description,
			tags=character.tags or [],
			status=character.status,
			updated_at=datetime.now(timezone.utc),
		)

	@staticmethod
	def _desired_thread_name(character: Character) -> str:
		base = f"Character: {character.name}".strip()
		if character.status is CharacterRole.INACTIVE:
			base = f"[Retired] {base}"
		return base[:90]

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

	@character.command(
		name="create",
		description="Start a DM wizard to create a new character profile.",
	)
	@app_commands.guild_only()
	async def character_create(self, interaction: discord.Interaction) -> None:
		if interaction.guild is None:
			await interaction.response.send_message(
				"This command can only be used inside a guild.", ephemeral=True
			)
			return

		member = interaction.user
		if not isinstance(member, discord.Member):
			await interaction.response.send_message(
				"Only guild members can create characters.", ephemeral=True
			)
			return

		if member.id in self._active_dm_sessions:
			await interaction.response.send_message(
				"You already have an active character creation session. Check your DMs or wait for it to finish.",
				ephemeral=True,
			)
			return

		self._active_dm_sessions.add(member.id)
		try:
			await interaction.response.send_message(
				"Check your DMs — I'll walk you through creating a character.",
				ephemeral=True,
			)

			try:
				dm_channel = await member.create_dm()
			except discord.Forbidden:
				await interaction.followup.send(
					"I can't send you direct messages. Enable DMs from server members and run `/character create` again.",
					ephemeral=True,
				)
				return

			session = CharacterCreationSession(self, interaction.guild, member, dm_channel)
			result = await session.run()

			if result.success:
				channel_info = (
					result.announcement_channel.mention
					if result.announcement_channel is not None
					else "the configured character channel"
				)
				await interaction.followup.send(
					f"Character `{result.character_name}` created successfully in {channel_info}.",
					ephemeral=True,
				)
			else:
				message = result.error or "Character creation cancelled."
				await interaction.followup.send(message, ephemeral=True)
		finally:
			self._active_dm_sessions.discard(member.id)

	@character.command(name="list", description="List your characters.")
	@app_commands.guild_only()
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

		characters = await self._owned_character_docs(interaction.guild, member)

		if not characters:
			await interaction.response.send_message(
				"You do not have any characters yet. Use `/character create` to start a new profile.",
				ephemeral=True,
			)
			return

		embed = discord.Embed(
			title=f"{member.display_name}'s Characters",
			colour=discord.Color.green(),
		)
		for doc in characters:
			char_id = self._normalize_character_id(doc.get("character_id"))
			status_value = doc.get("status") or CharacterRole.ACTIVE.value
			status_prefix = "[Retired] " if status_value != CharacterRole.ACTIVE.value else ""
			embed.add_field(
				name=f"{status_prefix}{char_id} — {doc.get('name', 'Unnamed')}",
				value=doc.get("ddb_link", "No sheet link"),
				inline=False,
			)

		await interaction.response.send_message(embed=embed, ephemeral=True)

	@character.command(
		name="edit", description="Update a character profile via DM."
	)
	@app_commands.describe(character="Character ID (e.g. CHAR0001)")
	@app_commands.guild_only()
	async def character_edit(
		self, interaction: discord.Interaction, character: str
	) -> None:
		if interaction.guild is None:
			await interaction.response.send_message(
				"This command can only be used inside a guild.", ephemeral=True
			)
			return

		member = interaction.user
		if not isinstance(member, discord.Member):
			await interaction.response.send_message(
				"Only guild members can update characters.", ephemeral=True
			)
			return

		character_obj = await self._fetch_character(interaction.guild, character)
		if character_obj is None:
			await interaction.response.send_message(
				f"Character `{character}` was not found.", ephemeral=True
			)
			return

		if not self._can_manage_character(member, character_obj):
			await interaction.response.send_message(
				"You do not have permission to modify this character.",
				ephemeral=True,
			)
			return

		if member.id in self._active_dm_sessions:
			await interaction.response.send_message(
				"You already have an active character session. Complete or cancel it before starting a new one.",
				ephemeral=True,
			)
			return

		await interaction.response.defer(ephemeral=True)

		try:
			dm_channel = await member.create_dm()
		except discord.Forbidden:
			await interaction.followup.send(
				"I can't send you direct messages. Enable DMs from server members and run `/character edit` again.",
				ephemeral=True,
			)
			return

		self._active_dm_sessions.add(member.id)
		try:
			session = CharacterUpdateSession(
				self, interaction.guild, member, dm_channel, character_obj
			)
			result = await session.run()
		finally:
			self._active_dm_sessions.discard(member.id)

		if not result.success or result.character is None:
			message = result.error or "Character update cancelled."
			await interaction.followup.send(message, ephemeral=True)
			return

		await send_demo_log(
			self.bot,
			interaction.guild,
			f"{member.mention} updated character `{result.character.name}` ({result.character.character_id}).",
		)

		note = result.note or ""
		response = (
			f"Character `{result.character.name}` updated successfully."
			+ (f"\n{note}" if note else "")
		)
		await interaction.followup.send(response, ephemeral=True)

	@character.command(
		name="state", description="Set a character's status to active or retired."
	)
	@app_commands.describe(
		character="Character ID (e.g. CHAR0001)",
		state="Choose the new state for the character.",
	)
	@app_commands.choices(
		state=[
			app_commands.Choice(name="Active", value="active"),
			app_commands.Choice(name="Retired", value="retired"),
		]
	)
	@app_commands.guild_only()
	async def character_state(
		self,
		interaction: discord.Interaction,
		character: str,
		state: app_commands.Choice[str],
	) -> None:
		target_status = (
			CharacterRole.ACTIVE if state.value == "active" else CharacterRole.INACTIVE
		)
		success_message = (
			"Character `{name}` has been restored to active status."
			if target_status is CharacterRole.ACTIVE
			else "Character `{name}` has been retired."
		)
		already_message = (
			"Character `{name}` is already active."
			if target_status is CharacterRole.ACTIVE
			else "Character `{name}` is already retired."
		)
		await self._handle_status_change(
			interaction,
			character,
			target_status=target_status,
			success_message=success_message,
			already_message=already_message,
		)

	@character.command(
		name="show",
		description="Get the announcement link for one of your characters.",
	)
	@app_commands.describe(character="Character ID (e.g. CHAR0001)")
	@app_commands.guild_only()
	async def character_show(
		self, interaction: discord.Interaction, character: str
	) -> None:
		if interaction.guild is None:
			await interaction.response.send_message(
				"This command can only be used inside a guild.", ephemeral=True
			)
			return

		member = interaction.user
		if not isinstance(member, discord.Member):
			await interaction.response.send_message(
				"Only guild members can inspect characters.", ephemeral=True
			)
			return

		character_obj = await self._fetch_character(interaction.guild, character)
		if character_obj is None:
			await interaction.response.send_message(
				f"Character `{character}` was not found.", ephemeral=True
			)
			return

		if not self._can_manage_character(member, character_obj):
			await interaction.response.send_message(
				"You do not have permission to view this character's announcement.",
				ephemeral=True,
			)
			return

		channel_id = character_obj.announcement_channel_id
		message_id = character_obj.announcement_message_id
		if not channel_id or not message_id:
			await interaction.response.send_message(
				"No announcement link is stored for this character.", ephemeral=True
			)
			return

		channel = interaction.guild.get_channel(channel_id)
		if channel is None:
			try:
				channel = await interaction.guild.fetch_channel(channel_id)
			except (discord.HTTPException, discord.Forbidden, discord.NotFound):
				channel = None
		if not isinstance(channel, discord.TextChannel):
			await interaction.response.send_message(
				"The stored announcement channel could not be accessed.", ephemeral=True
			)
			return

		jump_url: str = f"https://discord.com/channels/{interaction.guild.id}/{channel.id}/{message_id}"
		try:
			message = await channel.fetch_message(message_id)
			jump_url = message.jump_url
		except (discord.Forbidden, discord.NotFound, discord.HTTPException):
			pass

		embed = discord.Embed(
			title=f"{character_obj.name}",
			description=f"Character ID: `{character_obj.character_id}`",
			colour=discord.Colour.blurple(),
			timestamp=datetime.now(timezone.utc),
		)
		embed.add_field(
			name="Status",
			value=self._status_label(character_obj.status),
			inline=True,
		)
		embed.add_field(
			name="Channel",
			value=channel.mention,
			inline=True,
		)
		if character_obj.ddb_link:
			embed.add_field(name="Sheet", value=character_obj.ddb_link, inline=False)

		view = CharacterLinkView(jump_url)
		await interaction.response.send_message(
			"Here's your character announcement link:",
			ephemeral=True,
			embed=embed,
			view=view,
		)

	async def _character_autocomplete(
		self, interaction: discord.Interaction, current: str
	) -> List[app_commands.Choice[str]]:
		if interaction.guild is None or not isinstance(interaction.user, discord.Member):
			return []
		try:
			docs = await self._owned_character_docs(interaction.guild, interaction.user)
		except Exception:
			return []

		current_lower = current.lower()
		choices: List[app_commands.Choice[str]] = []
		for doc in docs:
			char_id = self._normalize_character_id(doc.get("character_id"))
			name = doc.get("name", "Unnamed")
			display = f"{name} ({char_id})"
			if current_lower and current_lower not in display.lower():
				continue
			choices.append(app_commands.Choice(name=display[:100], value=char_id))
			if len(choices) >= 25:
				break
		return choices

	@character_edit.autocomplete("character")
	async def character_edit_autocomplete(
		self, interaction: discord.Interaction, current: str
	) -> List[app_commands.Choice[str]]:
		return await self._character_autocomplete(interaction, current)

	@character_state.autocomplete("character")
	async def character_state_autocomplete(
		self, interaction: discord.Interaction, current: str
	) -> List[app_commands.Choice[str]]:
		return await self._character_autocomplete(interaction, current)

	@character_show.autocomplete("character")
	async def character_show_autocomplete(
		self, interaction: discord.Interaction, current: str
	) -> List[app_commands.Choice[str]]:
		return await self._character_autocomplete(interaction, current)


class CharacterSessionBase:
	def __init__(
		self,
		cog: "CharacterCommandsCog",
		guild: discord.Guild,
		member: discord.Member,
		dm_channel: discord.DMChannel,
	) -> None:
		self.cog = cog
		self.bot = cog.bot
		self.guild = guild
		self.member = member
		self.dm = dm_channel
		self.timeout = 180
		self.data: Dict[str, Optional[str]] = {}

	async def _safe_send(
		self,
		content: Optional[str] = None,
		*,
		embed: Optional[discord.Embed] = None,
		view: Optional[discord.ui.View] = None,
	) -> discord.Message:
		try:
			return await self.dm.send(content=content, embed=embed, view=view)
		except discord.Forbidden as exc:
			raise SessionMessagingError(
				"I can't send you direct messages anymore. Enable DMs and run the command again."
			) from exc
		except discord.HTTPException as exc:
			raise SessionMessagingError(f"Failed to send DM: {exc}") from exc

	async def _ask(
		self,
		prompt: str,
		*,
		required: bool,
		validator,
		allow_skip: bool = False,
		skip_message: Optional[str] = None,
		allow_clear: bool = False,
		clear_message: Optional[str] = None,
	) -> Optional[str]:
		instructions = ["Type `cancel` to stop."]
		if allow_skip:
			instructions.append(
				skip_message or "Type `skip` to keep the current value."
			)
		if allow_clear:
			instructions.append(
				clear_message or "Type `clear` to remove this value."
			)
		await self._safe_send(f"{prompt}\n" + " ".join(instructions))

		while True:
			try:
				message = await self.bot.wait_for(
					"message",
					timeout=self.timeout,
					check=lambda m: m.author.id == self.member.id
					and m.channel.id == self.dm.id,
				)
			except asyncio.TimeoutError as exc:
				raise SessionTimeout from exc

			content = message.content.strip()
			lower = content.lower()
			if lower == "cancel":
				raise SessionCancelled()
			if allow_clear and lower == "clear":
				return ""
			if allow_skip and lower == "skip":
				return None
			if not content:
				if required:
					await self._safe_send(
						"Please provide a response, or type `cancel`."
					)
					continue
				return None

			try:
				return validator(content) if validator else content
			except ValueError as exc:
				await self._safe_send(f"{exc}\nPlease try again.")

	def _build_embed_from_data(
		self,
		*,
		status: CharacterRole,
		updated_at: Optional[datetime] = None,
	) -> discord.Embed:
		return self.cog._build_character_embed(
			name=(self.data.get("name") or "Unnamed Character"),
			ddb_link=self.data.get("ddb_link"),
			character_thread_link=self.data.get("character_thread_link"),
			token_link=self.data.get("token_link"),
			art_link=self.data.get("art_link"),
			description=self.data.get("description"),
			tags=self._parse_tags(),
			status=status,
			updated_at=updated_at,
		)

	def _parse_tags(self) -> List[str]:
		raw = self.data.get("tags")
		if not raw:
			return []
		return [tag.strip() for tag in raw.split(",") if tag.strip()]

	@staticmethod
	def _normalize_optional(value: Optional[str]) -> Optional[str]:
		if value is None:
			return None
		trimmed = value.strip()
		return trimmed or None

	@staticmethod
	def _validate_name(value: str) -> str:
		name = value.strip()
		if not 2 <= len(name) <= 64:
			raise ValueError("Character name must be between 2 and 64 characters long.")
		return name

	@staticmethod
	def _validate_url(value: str) -> str:
		url = value.strip()
		parsed = urlparse(url)
		if parsed.scheme not in {"http", "https"} or not parsed.netloc:
			raise ValueError("Please provide a valid URL (http/https).")
		return url

	@staticmethod
	def _validate_description(value: str) -> str:
		text = value.strip()
		if len(text) > 500:
			raise ValueError("Description must be 500 characters or fewer.")
		return text

	@staticmethod
	def _validate_notes(value: str) -> str:
		text = value.strip()
		if len(text) > 500:
			raise ValueError("Notes must be 500 characters or fewer.")
		return text

	@staticmethod
	def _sanitize_tags(value: str) -> str:
		tags = [tag.strip() for tag in value.split(",") if tag.strip()]
		if len(tags) > 20:
			raise ValueError("Please provide 20 or fewer tags.")
		return ", ".join(tags)
@dataclass
class CharacterCreationResult:
	success: bool
	character_name: Optional[str] = None
	announcement_channel: Optional[discord.TextChannel] = None
	error: Optional[str] = None


@dataclass
class CharacterUpdateResult:
	success: bool
	character: Optional[Character] = None
	note: Optional[str] = None
	error: Optional[str] = None


class CharacterLinkView(discord.ui.View):
	def __init__(self, url: str):
		super().__init__(timeout=120)
		self.add_item(
			discord.ui.Button(label="Open Announcement", url=url)
		)


class CharacterConfirmView(discord.ui.View):
	def __init__(self, requester: discord.Member, *, timeout: int = 180):
		super().__init__(timeout=timeout)
		self.requester_id = requester.id
		self.result: Optional[str] = None

	@discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
	async def confirm(  # type: ignore[override]
		self, interaction: discord.Interaction, button: discord.ui.Button
	) -> None:
		if interaction.user.id != self.requester_id:
			await interaction.response.send_message(
				"This confirmation belongs to someone else.", ephemeral=True
			)
			return
		self.result = "confirm"
		await interaction.response.send_message(
			"Confirmed! Creating your character...", ephemeral=True
		)
		self.stop()

	@discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
	async def cancel(  # type: ignore[override]
		self, interaction: discord.Interaction, button: discord.ui.Button
	) -> None:
		if interaction.user.id != self.requester_id:
			await interaction.response.send_message(
				"This confirmation belongs to someone else.", ephemeral=True
			)
			return
		self.result = "cancel"
		await interaction.response.send_message(
			"Character creation cancelled.", ephemeral=True
		)
		self.stop()

	async def on_timeout(self) -> None:
		self.result = None
		self.stop()


class SessionCancelled(Exception):
	pass


class SessionTimeout(Exception):
	pass


class SessionMessagingError(Exception):
	def __init__(self, message: str):
		super().__init__(message)
		self.message = message


class CharacterCreationSession(CharacterSessionBase):
	def __init__(
		self,
		cog: CharacterCommandsCog,
		guild: discord.Guild,
		member: discord.Member,
		dm_channel: discord.DMChannel,
	) -> None:
		super().__init__(cog, guild, member, dm_channel)

	async def run(self) -> CharacterCreationResult:
		try:
			await self._safe_send(
				"Hello! Let's create your character. I'll ask a few questions — type `cancel` at any time to stop."
			)

			self.data["name"] = await self._ask(
				"**Step 1:** What's your character's name?",
				required=True,
				validator=self._validate_name,
			)
			self.data["ddb_link"] = await self._ask(
				"**Step 2:** Share the D&D Beyond (or sheet) link.",
				required=True,
				validator=self._validate_url,
			)
			self.data["character_thread_link"] = await self._ask(
				"**Step 3:** What's the forum/thread link for this character?",
				required=True,
				validator=self._validate_url,
			)
			self.data["token_link"] = await self._ask(
				"**Step 4:** Provide a token image link.",
				required=True,
				validator=self._validate_url,
			)
			self.data["art_link"] = await self._ask(
				"**Step 5:** Provide a character art link.",
				required=True,
				validator=self._validate_url,
			)
			self.data["description"] = await self._ask(
				"**Step 6:** Add an optional short description (max 500 characters).",
				required=False,
				validator=self._validate_description,
				allow_skip=True,
			)
			self.data["notes"] = await self._ask(
				"**Step 7:** Any private notes for staff? (max 500 characters).",
				required=False,
				validator=self._validate_notes,
				allow_skip=True,
			)
			self.data["tags"] = await self._ask(
				"**Step 8:** Optional tags (comma separated).",
				required=False,
				validator=self._sanitize_tags,
				allow_skip=True,
			)
		except SessionCancelled:
			await self._safe_send("Character creation cancelled. No data was saved.")
			return CharacterCreationResult(False, error="Character creation cancelled.")
		except SessionTimeout:
			await self._safe_send(
				"Timed out waiting for a response. Run `/character create` again when you're ready."
			)
			return CharacterCreationResult(
				False,
				error="Timed out waiting for a response. Run `/character create` again when you're ready.",
			)
		except SessionMessagingError as exc:
			return CharacterCreationResult(False, error=exc.message)

		tags = self._parse_tags()
		preview_embed = self._build_embed_from_data(status=CharacterRole.ACTIVE)

		try:
			await self._safe_send(
				"Here's a preview of what will be posted in the character channel:",
				embed=preview_embed,
			)
			notes = self.data.get("notes")
			if notes:
				await self._safe_send(
					"**Private notes (not shared publicly):**\n" + notes
				)

			view = CharacterConfirmView(self.member)
			message = await self._safe_send(
				"Confirm below to create the character, or cancel to stop.",
				view=view,
			)
		except SessionMessagingError as exc:
			return CharacterCreationResult(False, error=exc.message)

		await view.wait()
		try:
			await message.edit(view=None)
		except (discord.HTTPException, AttributeError):
			pass

		if view.result != "confirm":
			if view.result == "cancel":
				return CharacterCreationResult(
					False, error="Character creation cancelled."
				)
			return CharacterCreationResult(
				False,
				error="Confirmation timed out. Run `/character create` again when you're ready.",
			)

		try:
			return await self._persist_character(tags)
		except SessionMessagingError as exc:
			return CharacterCreationResult(False, error=exc.message)
		except Exception as exc:  # pragma: no cover - defensive
			logging.exception(
				"Unexpected error during character creation for %s: %s",
				self.member.id,
				exc,
			)
			return CharacterCreationResult(
				False,
				error="An unexpected error occurred while creating your character. Please try again later.",
			)

	async def _persist_character(self, tags: List[str]) -> CharacterCreationResult:
		channel, channel_error = self._resolve_character_channel()
		if channel is None:
			await self._safe_send(channel_error)
			return CharacterCreationResult(False, error=channel_error)

		try:
			user = await self.cog._get_cached_user(self.member)
		except RuntimeError as exc:
			logging.exception("Failed to resolve user during character create: %s", exc)
			await self._safe_send(
				"Internal error resolving your profile; please try again later."
			)
			return CharacterCreationResult(
				False,
				error="Internal error resolving your profile; please try again later.",
			)

		if not user.is_player:
			user.enable_player()

		char_id = self.cog._next_character_id(self.guild.id)
		description = self._normalize_optional(self.data.get("description"))
		notes = self._normalize_optional(self.data.get("notes"))
		character = Character(
			character_id=str(char_id),
			owner_id=user.user_id,
			name=self.data["name"] or "",
			ddb_link=self.data["ddb_link"] or "",
			character_thread_link=self.data["character_thread_link"] or "",
			token_link=self.data["token_link"] or "",
			art_link=self.data["art_link"] or "",
			description=description,
			notes=notes,
			tags=tags,
			created_at=datetime.now(timezone.utc),
			guild_id=self.guild.id,
			status=CharacterRole.ACTIVE,
		)

		try:
			character.validate_character()
		except ValueError as exc:
			await self._safe_send(f"Character validation failed: {exc}")
			return CharacterCreationResult(
				False, error=f"Character validation failed: {exc}"
			)

		if user.player is None:
			user.enable_player()
		if user.player is not None and char_id not in user.player.characters:
			user.player.characters.append(CharacterID.parse(str(char_id)))

		public_embed = self.cog._build_character_embed_from_model(character)
		try:
			announcement = await channel.send(
				content=f"{self.member.mention} created a new character!",
				embed=public_embed,
			)
		except discord.Forbidden:
			error = (
				f"I don't have permission to post in {channel.mention}. "
				"Ask an admin to fix my channel permissions and try again."
			)
			await self._safe_send(error)
			return CharacterCreationResult(False, error=error)
		except discord.HTTPException as exc:
			error = f"Failed to post in {channel.mention}: {exc}"
			await self._safe_send(error)
			return CharacterCreationResult(False, error=error)

		await send_demo_log(
			self.cog.bot,
			self.guild,
			f"{self.member.mention} created character `{character.name}` ({char_id})",
		)

		thread = None
		thread_note = None
		thread_name = f"Character: {character.name}"[:90]
		thread_parent = announcement.channel
		if isinstance(thread_parent, discord.TextChannel):
			thread = await self._create_character_thread(
				thread_parent, announcement, thread_name
			)
			if thread is None:
				thread_note = (
					"I couldn't create a private onboarding thread. Grant me the **Create Private Threads** permission or allow thread creation in the configured channel."
				)
		else:
			thread_note = "Character announcements are posted in a channel that does not support threads."

		if isinstance(announcement.channel, discord.TextChannel):
			character.announcement_channel_id = announcement.channel.id
		character.announcement_message_id = announcement.id
		if thread is not None:
			character.onboarding_thread_id = thread.id

		self.cog._persist_character(self.guild.id, character)
		await self.cog.bot.dirty_data.put((self.guild.id, self.member.id))

		summary_lines = [
			f"Character `{character.name}` (`{char_id}`) created!",
			f"Announcement: {announcement.jump_url}",
		]
		if thread is not None:
			thread_link = f"https://discord.com/channels/{self.guild.id}/{thread.id}"
			summary_lines.append(f"Onboarding thread: {thread_link}")
		if thread_note:
			summary_lines.append(thread_note)

		await self._safe_send("\n".join(summary_lines))

		return CharacterCreationResult(
			True,
			character_name=character.name,
			announcement_channel=announcement.channel
			if isinstance(announcement.channel, discord.TextChannel)
			else None,
		)


class CharacterUpdateSession(CharacterSessionBase):
	def __init__(
		self,
		cog: CharacterCommandsCog,
		guild: discord.Guild,
		member: discord.Member,
		dm_channel: discord.DMChannel,
		character: Character,
	) -> None:
		super().__init__(cog, guild, member, dm_channel)
		self.character = character
		self.status = character.status
		self.data = {
			"name": character.name,
			"ddb_link": character.ddb_link,
			"character_thread_link": character.character_thread_link,
			"token_link": character.token_link,
			"art_link": character.art_link,
			"description": character.description,
			"notes": character.notes,
			"tags": ", ".join(character.tags) if character.tags else None,
		}

	def _apply_response(self, key: str, response: Optional[str]) -> None:
		if response is None:
			return
		self.data[key] = response if response != "" else None

	async def run(self) -> CharacterUpdateResult:
		try:
			await self._safe_send(
				"Let's update your character. For each prompt, type a new value, `skip` to keep the current value, or `clear` to remove optional fields."
			)
			current_embed = self.cog._build_character_embed_from_model(self.character)
			await self._safe_send("Current profile:", embed=current_embed)

			responses = [
				(
					"name",
					"**Step 1:** Update the character name (or `skip`).",
					self._validate_name,
					True,
					False,
				),
				(
					"ddb_link",
					"**Step 2:** Update the D&D Beyond (or sheet) link.",
					self._validate_url,
					True,
					False,
				),
				(
					"character_thread_link",
					"**Step 3:** Update the forum/thread link.",
					self._validate_url,
					True,
					False,
				),
				(
					"token_link",
					"**Step 4:** Update the token image link.",
					self._validate_url,
					True,
					False,
				),
				(
					"art_link",
					"**Step 5:** Update the character art link.",
					self._validate_url,
					True,
					False,
				),
			]

			for key, prompt, validator, required, allow_clear in responses:
				response = await self._ask(
					prompt,
					required=required,
					validator=validator,
					allow_skip=True,
					skip_message="Type `skip` to keep the current value.",
					allow_clear=allow_clear,
				)
				self._apply_response(key, response)

			optional_prompts = [
				(
					"description",
					"**Step 6:** Update the short description (max 500 characters).",
					self._validate_description,
				),
				(
					"notes",
					"**Step 7:** Update private notes for staff (max 500 characters).",
					self._validate_notes,
				),
				(
					"tags",
					"**Step 8:** Update tags (comma separated).",
					self._sanitize_tags,
				),
			]

			for key, prompt, validator in optional_prompts:
				response = await self._ask(
					prompt,
					required=False,
					validator=validator,
					allow_skip=True,
					skip_message="Type `skip` to keep the current value.",
					allow_clear=True,
					clear_message="Type `clear` to remove this value.",
				)
				self._apply_response(key, response)
		except SessionCancelled:
			await self._safe_send("Character update cancelled. No changes were applied.")
			return CharacterUpdateResult(success=False, error="Character update cancelled.")
		except SessionTimeout:
			await self._safe_send(
				"Timed out waiting for a response. Run `/character edit` again when you're ready."
			)
			return CharacterUpdateResult(
				success=False,
				error="Timed out waiting for a response. Run `/character edit` again when you're ready.",
			)
		except SessionMessagingError as exc:
			return CharacterUpdateResult(success=False, error=exc.message)

		tags = self._parse_tags()
		preview_embed = self._build_embed_from_data(
			status=self.status, updated_at=datetime.now(timezone.utc)
		)

		try:
			await self._safe_send("Preview of your updated character:", embed=preview_embed)
			notes = self._normalize_optional(self.data.get("notes"))
			if notes:
				await self._safe_send("**Private notes (not shared publicly):**\n" + notes)

			view = CharacterConfirmView(self.member)
			message = await self._safe_send(
				"Confirm below to apply these updates, or cancel to stop.", view=view
			)
		except SessionMessagingError as exc:
			return CharacterUpdateResult(success=False, error=exc.message)

		await view.wait()
		try:
			await message.edit(view=None)
		except (discord.HTTPException, AttributeError):
			pass

		if view.result != "confirm":
			if view.result == "cancel":
				return CharacterUpdateResult(success=False, error="Character update cancelled.")
			return CharacterUpdateResult(
				success=False,
				error="Confirmation timed out. Run `/character edit` again when you're ready.",
			)

		return await self._apply_updates(tags)

	async def _apply_updates(self, tags: List[str]) -> CharacterUpdateResult:
		character = self.character
		name = self.data.get("name")
		if name is not None:
			character.name = name
		for field in (
			"ddb_link",
			"character_thread_link",
			"token_link",
			"art_link",
		):
			value = self.data.get(field)
			if value is not None:
				setattr(character, field, value or "")

		description = self._normalize_optional(self.data.get("description"))
		notes = self._normalize_optional(self.data.get("notes"))
		character.description = description
		character.notes = notes
		character.tags = tags
		character.status = self.status
		character.guild_id = self.guild.id

		try:
			character.validate_character()
		except ValueError as exc:
			await self._safe_send(f"Character validation failed: {exc}")
			return CharacterUpdateResult(False, error=f"Character validation failed: {exc}")

		self.cog._persist_character(self.guild.id, character)
		note = await self.cog._update_character_announcement(self.guild, character)

		summary = [
			f"Character `{character.name}` (`{character.character_id}`) updated!",
		]
		if note:
			summary.append(note)
		await self._safe_send("\n".join(summary))

		return CharacterUpdateResult(
			success=True,
			character=character,
			note=note,
		)

	async def _create_character_thread(
		self,
		channel: discord.TextChannel,
		announcement: discord.Message,
		thread_name: str,
	) -> Optional[discord.Thread]:
		try:
			thread = await channel.create_thread(
				name=thread_name,
				type=discord.ChannelType.private_thread,
				auto_archive_duration=channel.default_auto_archive_duration or 1440,
				reason="Character onboarding",
			)
		except (discord.Forbidden, discord.HTTPException):
			return None

		try:
			await thread.add_user(self.member)
		except discord.HTTPException:
			pass

		try:
			await thread.send(
				f"Onboarding thread for {self.member.mention}. "
				f"Announcement: {announcement.jump_url}"
			)
		except discord.HTTPException:
			pass

		return thread

	def _resolve_character_channel(
		self,
	) -> tuple[Optional[discord.TextChannel], str]:
		settings = guild_settings_store.fetch_settings(self.guild.id) or {}
		channel_id = settings.get("character_commands_channel_id")
		if channel_id is None:
			return (
				None,
				"No character commands channel is configured. Ask an admin to run `/setup character` and try again.",
			)

		try:
			candidate = self.guild.get_channel(int(channel_id))
		except (TypeError, ValueError):
			candidate = None

		if not isinstance(candidate, discord.TextChannel):
			return (
				None,
				"The configured character channel is missing or not a text channel. Ask an admin to rerun `/setup character`.",
			)

		me = self.guild.me
		if me is None:
			return (
				None,
				"I couldn't resolve my bot member in this guild. Try again once I'm fully connected.",
			)

		perms = candidate.permissions_for(me)
		if not perms.send_messages:
			return (
				None,
				f"I need permission to send messages in {candidate.mention}. Update my permissions and try again.",
			)
		if not (perms.create_private_threads or perms.manage_threads):
			return (
				None,
				f"I need **Create Private Threads** permission in {candidate.mention} to start onboarding threads.",
			)

		return candidate, ""

	async def _ask(
		self,
		prompt: str,
		*,
		required: bool,
		validator,
		allow_skip: bool = False,
	) -> Optional[str]:
		instructions = ["Type `cancel` to stop."]
		if not required and allow_skip:
			instructions.append("Type `skip` to leave this blank.")
		await self._safe_send(f"{prompt}\n" + " ".join(instructions))

		while True:
			try:
				message = await self.bot.wait_for(
					"message",
					timeout=self.timeout,
					check=lambda m: m.author.id == self.member.id
					and m.channel.id == self.dm.id,
				)
			except asyncio.TimeoutError as exc:
				raise SessionTimeout from exc

			content = message.content.strip()
			if content.lower() == "cancel":
				raise SessionCancelled()
			if allow_skip and content.lower() == "skip":
				return None
			if not content:
				if required:
					await self._safe_send(
						"Please provide a response or type `cancel`."
					)
					continue
				return None

			try:
				return validator(content) if validator else content
			except ValueError as exc:
				await self._safe_send(f"{exc}\nPlease try again.")

	async def _safe_send(
		self,
		content: Optional[str] = None,
		*,
		embed: Optional[discord.Embed] = None,
		view: Optional[discord.ui.View] = None,
	) -> discord.Message:
		try:
			return await self.dm.send(content=content, embed=embed, view=view)
		except discord.Forbidden as exc:
			raise SessionMessagingError(
				"I can't send you direct messages anymore. Enable DMs and run the command again."
			) from exc
		except discord.HTTPException as exc:
			raise SessionMessagingError(f"Failed to send DM: {exc}") from exc

	def _parse_tags(self) -> List[str]:
		raw = self.data.get("tags")
		if not raw:
			return []
		return [tag.strip() for tag in raw.split(",") if tag.strip()]

	@staticmethod
	def _validate_name(value: str) -> str:
		name = value.strip()
		if not 2 <= len(name) <= 64:
			raise ValueError("Character name must be between 2 and 64 characters long.")
		return name

	@staticmethod
	def _validate_url(value: str) -> str:
		url = value.strip()
		parsed = urlparse(url)
		if parsed.scheme not in {"http", "https"} or not parsed.netloc:
			raise ValueError("Please provide a valid URL (http/https).")
		return url

	@staticmethod
	def _validate_description(value: str) -> str:
		text = value.strip()
		if len(text) > 500:
			raise ValueError("Description must be 500 characters or fewer.")
		return text

	@staticmethod
	def _validate_notes(value: str) -> str:
		text = value.strip()
		if len(text) > 500:
			raise ValueError("Notes must be 500 characters or fewer.")
		return text

	@staticmethod
	def _sanitize_tags(value: str) -> str:
		tags = [tag.strip() for tag in value.split(",") if tag.strip()]
		if len(tags) > 20:
			raise ValueError("Please provide 20 or fewer tags.")
		return ", ".join(tags)


async def setup(bot: commands.Bot):
	await bot.add_cog(CharacterCommandsCog(bot))
