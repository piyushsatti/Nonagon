from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.database import db_client
from app.bot.services import guild_settings_store
from app.domain.models.UserModel import User
from app.infra.mongo.guild_adapter import upsert_user_sync
from app.infra.mongo.users_repo import UsersRepoMongo


class GuildCommandsCog(commands.Cog):
	"""Slash command group for guild-scoped Nonagon configuration utilities."""

	guild = app_commands.Group(
		name="guild", description="Manage Nonagon configuration for this Discord guild."
	)

	def __init__(self, bot: commands.Bot) -> None:
		self.bot = bot
		self.users_repo = UsersRepoMongo()

	@guild.command(name="help", description="Learn what the /guild commands do.")
	@app_commands.guild_only()
	async def guild_help(self, interaction: discord.Interaction) -> None:
		embed = discord.Embed(
			title="Nonagon Guild Commands",
			description="Utilities to configure and inspect the Nonagon bot for this server.",
			colour=discord.Colour.blurple(),
		)
		embed.add_field(
			name="/guild setup",
			value=(
				"Select existing channels and roles for quest commands, status logs, and server tagging. "
				"Requires **Manage Guild**."
			),
			inline=False,
		)
		embed.add_field(
			name="/guild refresh",
			value=(
				"Sync the current member list into the database and flag members with the configured server tag."
			),
			inline=False,
		)
		embed.add_field(
			name="/guild stats",
			value="Show quick stats about this server and how Nonagon sees it.",
			inline=False,
		)
		embed.set_footer(text="Need to clear optional fields? See the /guild setup descriptions.")

		await interaction.response.send_message(embed=embed, ephemeral=True)

	@guild.command(name="setup", description="Configure Nonagon resources for this guild.")
	@app_commands.describe(
		quest_commands_channel="Channel where quest commands default to posting.",
		summary_commands_channel="Channel for summary commands.",
		character_commands_channel="Channel for character commands.",
		log_channel="Channel where diagnostic bot logs will be sent.",
		allowed_roles=(
			"Mention roles (comma or space separated) that can run advanced quest commands. "
			"Type 'none' to clear."
		),
		server_tag_role="Role that marks members with the server tag (optional).",
		server_tag_pattern="Text to search for in nicknames/display names to mark server-tagged members.",
		server_tag_mention_role="Role to mention when referencing server-tagged members.",
		clear_server_tag_role="Set true to remove the stored server tag role.",
		clear_server_tag_mention_role="Set true to remove the stored server tag mention role.",
	)
	@app_commands.guild_only()
	@app_commands.checks.has_permissions(manage_guild=True)
	async def guild_setup(
		self,
		interaction: discord.Interaction,
		quest_commands_channel: discord.TextChannel,
		summary_commands_channel: discord.TextChannel,
		character_commands_channel: discord.TextChannel,
		log_channel: discord.TextChannel,
		allowed_roles: Optional[str] = None,
		server_tag_role: Optional[discord.Role] = None,
		server_tag_pattern: Optional[str] = None,
		server_tag_mention_role: Optional[discord.Role] = None,
		clear_server_tag_role: bool = False,
		clear_server_tag_mention_role: bool = False,
	) -> None:
		if interaction.guild is None:
			await interaction.response.send_message(
				"This command can only be used inside a guild.", ephemeral=True
			)
			return

		await interaction.response.defer(ephemeral=True, thinking=True)

		guild = interaction.guild
		existing = guild_settings_store.fetch_settings(guild.id) or {}
		namespace: Dict[str, object] = getattr(
			getattr(interaction, "namespace", None), "__dict__", {}
		)

		config = dict(existing)
		config.update(
			{
				"guild_id": guild.id,
				"quest_commands_channel_id": quest_commands_channel.id,
				"quest_commands_channel_name": quest_commands_channel.name,
				"summary_commands_channel_id": summary_commands_channel.id,
				"summary_commands_channel_name": summary_commands_channel.name,
				"character_commands_channel_id": character_commands_channel.id,
				"character_commands_channel_name": character_commands_channel.name,
				"log_channel_id": log_channel.id,
				"log_channel_name": log_channel.name,
				"configured_by": interaction.user.id,
			}
		)
		if "configured_at" not in config:
			config["configured_at"] = datetime.now(timezone.utc)

		if allowed_roles is not None or "allowed_roles" in namespace:
			try:
				allowed_seq = self._parse_role_list(guild, allowed_roles)
			except ValueError as exc:
				await interaction.followup.send(str(exc), ephemeral=True)
				return
			config["allowed_role_ids"] = [role.id for role in allowed_seq]
			config["allowed_role_names"] = [role.name for role in allowed_seq]

		if clear_server_tag_role:
			config.pop("server_tag_role_id", None)
			config.pop("server_tag_role_name", None)
		elif server_tag_role is not None or "server_tag_role" in namespace:
			if server_tag_role is not None:
				config["server_tag_role_id"] = server_tag_role.id
				config["server_tag_role_name"] = server_tag_role.name

		if server_tag_pattern is not None or "server_tag_pattern" in namespace:
			pattern = (server_tag_pattern or "").strip()
			if pattern:
				config["server_tag_pattern"] = pattern
			else:
				config.pop("server_tag_pattern", None)

		if clear_server_tag_mention_role:
			config.pop("server_tag_mention_role_id", None)
			config.pop("server_tag_mention_role_name", None)
		elif server_tag_mention_role is not None or "server_tag_mention_role" in namespace:
			if server_tag_mention_role is not None:
				config["server_tag_mention_role_id"] = server_tag_mention_role.id
				config["server_tag_mention_role_name"] = server_tag_mention_role.name

		for channel in (
			quest_commands_channel,
			summary_commands_channel,
			character_commands_channel,
			log_channel,
		):
			if not channel.permissions_for(guild.me).send_messages:
				await interaction.followup.send(
					f"I need the **Send Messages** permission in {channel.mention} to store it.",
					ephemeral=True,
				)
				return

		guild_settings_store.save_settings(guild.id, config)

		embed = discord.Embed(
			title="Guild configuration saved",
			colour=discord.Colour.green(),
			timestamp=datetime.now(timezone.utc),
		)
		embed.add_field(
			name="Quest commands channel", value=quest_commands_channel.mention, inline=False
		)
		embed.add_field(
			name="Summary commands channel",
			value=summary_commands_channel.mention,
			inline=False,
		)
		embed.add_field(
			name="Character commands channel",
			value=character_commands_channel.mention,
			inline=False,
		)
		embed.add_field(name="Log channel", value=log_channel.mention, inline=False)

		allowed_names = config.get("allowed_role_names") or []
		if allowed_names:
			embed.add_field(
				name="Allowed roles",
				value=", ".join(f"`{name}`" for name in allowed_names),
				inline=False,
			)
		else:
			embed.add_field(name="Allowed roles", value="None configured", inline=False)

		server_tag_role_name = config.get("server_tag_role_name")
		if server_tag_role_name:
			embed.add_field(
				name="Server tag role",
				value=f"`{server_tag_role_name}`",
				inline=False,
			)
		else:
			embed.add_field(name="Server tag role", value="Not set", inline=False)

		pattern = config.get("server_tag_pattern")
		embed.add_field(
			name="Server tag pattern",
			value=f"`{pattern}`" if pattern else "Not set",
			inline=False,
		)

		mention_role_name = config.get("server_tag_mention_role_name")
		if mention_role_name:
			embed.add_field(
				name="Server tag mention role",
				value=f"`{mention_role_name}`",
				inline=False,
			)
		else:
			embed.add_field(
				name="Server tag mention role", value="Not set", inline=False
			)

		if existing.get("managed_role_id"):
			embed.set_footer(
				text="Note: managed_role is deprecated; allowed_roles now control elevated access."
			)
		else:
			embed.set_footer(text="Configuration stored successfully.")

		await interaction.followup.send(embed=embed, ephemeral=True)

	@guild.command(
		name="refresh",
		description="Sync members into the database and flag server-tagged users.",
	)
	@app_commands.guild_only()
	@app_commands.checks.has_permissions(manage_guild=True)
	async def guild_refresh(self, interaction: discord.Interaction) -> None:
		if interaction.guild is None:
			await interaction.response.send_message(
				"This command can only be used inside a guild.", ephemeral=True
			)
			return

		await interaction.response.defer(ephemeral=True, thinking=True)

		guild = interaction.guild
		settings = guild_settings_store.fetch_settings(guild.id) or {}
		server_tag_role_id = self._coerce_int(settings.get("server_tag_role_id"))
		server_tag_pattern = settings.get("server_tag_pattern")

		processed = 0
		created = 0
		updated = 0
		tagged = 0

		try:
			async for member in guild.fetch_members(limit=None):
				processed += 1
				has_tag = self._member_has_server_tag(
					member, server_tag_role_id, server_tag_pattern
				)
				if has_tag:
					tagged += 1

				existing_user = await self.users_repo.get_by_discord_id(
					guild.id, str(member.id)
				)
				if existing_user is None:
					user = User.from_member(member)
					created += 1
				else:
					user = existing_user
					updated += 1
				user.guild_id = guild.id
				user.discord_id = str(member.id)
				user.has_server_tag = has_tag
				if member.joined_at:
					user.joined_at = member.joined_at

				await asyncio.to_thread(upsert_user_sync, db_client, guild.id, user)
		except (discord.Forbidden, discord.HTTPException) as exc:
			await interaction.followup.send(
				f"Failed to fetch members: {exc}", ephemeral=True
			)
			return

		embed = discord.Embed(
			title="Member refresh complete",
			colour=discord.Colour.green(),
			timestamp=datetime.now(timezone.utc),
		)
		embed.add_field(name="Processed members", value=str(processed))
		embed.add_field(name="Created users", value=str(created))
		embed.add_field(name="Updated users", value=str(updated))
		embed.add_field(name="Server-tagged", value=str(tagged))

		await interaction.followup.send(embed=embed, ephemeral=True)

	@guild.command(name="stats", description="Show Nonagon stats for this guild.")
	@app_commands.guild_only()
	async def guild_stats(self, interaction: discord.Interaction) -> None:
		if interaction.guild is None:
			await interaction.response.send_message(
				"This command can only be used inside a guild.", ephemeral=True
			)
			return

		guild = interaction.guild
		settings = guild_settings_store.fetch_settings(guild.id) or {}
		allowed_role_ids: List[int] = []
		for raw_id in settings.get("allowed_role_ids") or []:
			coerced = self._coerce_int(raw_id)
			if coerced is not None:
				allowed_role_ids.append(coerced)
		server_tag_role_id = self._coerce_int(settings.get("server_tag_role_id"))

		total_members = guild.member_count or len(guild.members)
		humans = sum(1 for m in guild.members if not m.bot)
		bots = total_members - humans

		text_channels = sum(
			1 for channel in guild.channels if isinstance(channel, discord.TextChannel)
		)

		roles_count = len(guild.roles)

		allowed_role_members = 0
		if allowed_role_ids:
			role_set = {guild.get_role(int(rid)) for rid in allowed_role_ids}
			role_set = {role for role in role_set if role is not None}
			for member in guild.members:
				if any(role in member.roles for role in role_set):
					allowed_role_members += 1

		server_tagged_count = 0
		if server_tag_role_id:
			role = guild.get_role(int(server_tag_role_id))
			if role:
				server_tagged_count = len(role.members)

		embed = discord.Embed(
			title=f"{guild.name} overview",
			colour=discord.Colour.blurple(),
			timestamp=datetime.now(timezone.utc),
		)
		embed.add_field(name="Members", value=str(total_members))
		embed.add_field(name="Humans", value=str(humans))
		embed.add_field(name="Bots", value=str(bots))
		embed.add_field(name="Text channels", value=str(text_channels))
		embed.add_field(name="Roles", value=str(roles_count))

		if allowed_role_ids:
			embed.add_field(
				name="Allowed role coverage", value=str(allowed_role_members), inline=False
			)
		if server_tag_role_id:
			embed.add_field(
				name="Server-tagged members", value=str(server_tagged_count), inline=False
			)

		await interaction.response.send_message(embed=embed, ephemeral=True)

	def _member_has_server_tag(
		self,
		member: discord.Member,
		role_id: Optional[int],
		pattern: Optional[str],
	) -> bool:
		if role_id is not None:
			role = member.guild.get_role(int(role_id))
			if role and role in member.roles:
				return True
		if pattern:
			target = (member.nick or member.display_name or member.name or "").lower()
			if pattern.lower() in target:
				return True
		return False

	@staticmethod
	def _coerce_int(raw: Optional[object]) -> Optional[int]:
		try:
			if raw is None:
				return None
			return int(raw)
		except (TypeError, ValueError):
			return None

	def _parse_role_list(
		self, guild: discord.Guild, raw: Optional[str]
	) -> Sequence[discord.Role]:
		if raw is None:
			return []
		normalized = raw.strip()
		if not normalized or normalized.lower() in {"none", "null", "empty"}:
			return []

		tokens = [token for token in normalized.replace(",", " ").split() if token]
		roles: List[discord.Role] = []
		missing: List[str] = []
		for token in tokens:
			role: Optional[discord.Role] = None
			if token.startswith("<@&") and token.endswith(">"):
				try:
					role_id = int(token[3:-1])
				except ValueError:
					role_id = None
				if role_id is not None:
					role = guild.get_role(role_id)
			if role is None:
				role = discord.utils.find(
					lambda r: r.name.lower() == token.lower(), guild.roles
				)
			if role is None:
				missing.append(token)
				continue
			if role not in roles:
				roles.append(role)

		if missing:
			raise ValueError(
				f"Unknown role(s): {', '.join(missing)}. Mention roles or provide exact names."
			)
		return roles


async def setup(bot: commands.Bot) -> None:
	await bot.add_cog(GuildCommandsCog(bot))
