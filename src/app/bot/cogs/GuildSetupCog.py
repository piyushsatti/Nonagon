from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.services import guild_settings_store

SETUP_REASON = "Configured by Nonagon /setup command"
ROLE_NAME = "Quest Manager"
SIGNUPS_CHANNEL_NAME = "quest-signups"
LOG_CHANNEL_NAME = "nonagon-bot-logs"


class GuildSetupCog(commands.Cog):
	"""Administrative commands to bootstrap Nonagon in a new guild."""

	def __init__(self, bot: commands.Bot) -> None:
		self.bot = bot

	async def cog_app_command_error(
		self, interaction: discord.Interaction, error: app_commands.AppCommandError
	) -> None:
		if isinstance(error, app_commands.AppCommandError):
			if isinstance(error, app_commands.MissingPermissions):
				if interaction.response.is_done():
					await interaction.followup.send(
						"You need the **Manage Guild** permission to run this command.",
						ephemeral=True,
					)
				else:
					await interaction.response.send_message(
						"You need the **Manage Guild** permission to run this command.",
						ephemeral=True,
					)
				return
			if isinstance(error, app_commands.NoPrivateMessage):
				if interaction.response.is_done():
					await interaction.followup.send(
						"This command can only be used inside a guild.", ephemeral=True
					)
				else:
					await interaction.response.send_message(
						"This command can only be used inside a guild.", ephemeral=True
					)
				return
		raise error

	@app_commands.command(
		name="setup", description="Configure the Nonagon bot resources for this guild."
	)
	@app_commands.describe(force="Recreate settings even if configuration already exists")
	@app_commands.checks.has_permissions(manage_guild=True)
	async def setup_command(
		self, interaction: discord.Interaction, force: Optional[bool] = False
	) -> None:
		if interaction.guild is None:
			raise app_commands.NoPrivateMessage()

		await interaction.response.defer(ephemeral=True, thinking=True)
		guild = interaction.guild
		existing = guild_settings_store.fetch_settings(guild.id)

		if existing and not force:
			embed = self._build_summary_embed(guild, existing)
			embed.title = "Nonagon setup already completed"
			embed.set_footer(text="Re-run with /setup force:true to refresh resources.")
			await interaction.followup.send(embed=embed, ephemeral=True)
			return

		role = await self._ensure_role(
			guild, existing.get("managed_role_id") if existing else None
		)
		signups_channel = await self._ensure_text_channel(
			guild,
			SIGNUPS_CHANNEL_NAME,
			existing.get("signups_channel_id") if existing else None,
		)
		log_channel = await self._ensure_text_channel(
			guild,
			LOG_CHANNEL_NAME,
			existing.get("log_channel_id") if existing else None,
		)

		config = {
			"guild_id": guild.id,
			"managed_role_id": role.id,
			"managed_role_name": role.name,
			"signups_channel_id": signups_channel.id,
			"signups_channel_name": signups_channel.name,
			"log_channel_id": log_channel.id,
			"log_channel_name": log_channel.name,
			"configured_by": interaction.user.id,
			"configured_at": datetime.now(timezone.utc),
		}
		guild_settings_store.save_settings(guild.id, config)

		embed = self._build_summary_embed(guild, config)
		embed.title = "Nonagon setup completed"
		if force:
			embed.set_footer(text="Existing settings replaced (force mode).")
		await interaction.followup.send(embed=embed, ephemeral=True)

	@app_commands.command(
		name="setup_status", description="View the current Nonagon configuration for this guild."
	)
	async def setup_status(self, interaction: discord.Interaction) -> None:
		if interaction.guild is None:
			raise app_commands.NoPrivateMessage()

		settings = guild_settings_store.fetch_settings(interaction.guild.id)
		if not settings:
			await interaction.response.send_message(
				"No setup information found for this guild. Run `/setup` to configure Nonagon.",
				ephemeral=True,
			)
			return

		embed = self._build_summary_embed(interaction.guild, settings)
		embed.title = "Nonagon setup status"
		await interaction.response.send_message(embed=embed, ephemeral=True)

	@app_commands.command(
		name="setup_reset",
		description="Clear stored Nonagon setup data without deleting roles/channels.",
	)
	@app_commands.checks.has_permissions(manage_guild=True)
	async def setup_reset(self, interaction: discord.Interaction) -> None:
		if interaction.guild is None:
			raise app_commands.NoPrivateMessage()

		existed = guild_settings_store.delete_settings(interaction.guild.id)
		if existed:
			message = (
				"Stored configuration was cleared. Existing roles/channels were left untouched. "
				"Run `/setup` again to regenerate settings."
			)
		else:
			message = "No stored configuration was found for this guild."

		await interaction.response.send_message(message, ephemeral=True)

	async def _ensure_role(
		self, guild: discord.Guild, role_id: Optional[int]
	) -> discord.Role:
		if role_id:
			role = guild.get_role(role_id)
			if role is not None:
				return role

		existing = discord.utils.get(guild.roles, name=ROLE_NAME)
		if existing:
			return existing

		logging.info("Creating role '%s' in guild %s", ROLE_NAME, guild.id)
		return await guild.create_role(name=ROLE_NAME, reason=SETUP_REASON)

	async def _ensure_text_channel(
		self, guild: discord.Guild, name: str, channel_id: Optional[int]
	) -> discord.TextChannel:
		if channel_id:
			channel = guild.get_channel(channel_id)
			if isinstance(channel, discord.TextChannel):
				return channel

		existing = discord.utils.get(guild.text_channels, name=name)
		if existing:
			return existing

		logging.info("Creating channel '%s' in guild %s", name, guild.id)
		channel = await guild.create_text_channel(name=name, reason=SETUP_REASON)
		return channel

	def _build_summary_embed(
		self, guild: discord.Guild, settings: dict
	) -> discord.Embed:
		embed = discord.Embed(
			colour=discord.Color.blurple(),
			timestamp=settings.get("configured_at") or settings.get("updated_at"),
		)

		role = guild.get_role(settings.get("managed_role_id"))
		signups = guild.get_channel(settings.get("signups_channel_id", 0))
		logs = guild.get_channel(settings.get("log_channel_id", 0))
		configured_by = settings.get("configured_by")
		configured_member = (
			guild.get_member(configured_by) if configured_by is not None else None
		)

		embed.add_field(
			name="Quest Manager role",
			value=role.mention if role else settings.get("managed_role_name", "N/A"),
			inline=False,
		)
		embed.add_field(
			name="Sign-ups channel",
			value=signups.mention
			if isinstance(signups, discord.TextChannel)
			else f"#{settings.get('signups_channel_name', 'N/A')}",
			inline=False,
		)
		embed.add_field(
			name="Log channel",
			value=logs.mention
			if isinstance(logs, discord.TextChannel)
			else f"#{settings.get('log_channel_name', 'N/A')}",
			inline=False,
		)

		if configured_member:
			embed.set_footer(text=f"Configured by {configured_member.display_name}")
		elif configured_by:
			embed.set_footer(text=f"Configured by user ID {configured_by}")

		return embed


async def setup(bot: commands.Bot) -> None:
	await bot.add_cog(GuildSetupCog(bot))
