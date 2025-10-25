from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands


class AdminCommandsCog(commands.Cog):
	"""Administrative slash commands for rapid iteration helpers."""

	admin = app_commands.Group(
		name="admin", description="Administrative utilities for Nonagon."
	)

	def __init__(self, bot: commands.Bot) -> None:
		self.bot = bot

	@admin.command(
		name="sync_commands",
		description="Force a slash-command sync for this guild (or every guild).",
	)
	@app_commands.describe(all_guilds="Sync every guild the bot is in (defaults to current guild only).")
	@app_commands.guild_only()
	@app_commands.checks.has_permissions(manage_guild=True)
	async def sync_commands(
		self, interaction: discord.Interaction, all_guilds: Optional[bool] = False
	) -> None:
		await interaction.response.defer(ephemeral=True, thinking=True)

		target_ids: set[int]
		if all_guilds:
			target_ids = {guild.id for guild in self.bot.guilds}
			if not target_ids:
				await interaction.followup.send(
					"I'm not connected to any guilds yet; nothing to sync.",
					ephemeral=True,
				)
				return
		else:
			if interaction.guild is None:
				await interaction.followup.send(
					"This command can only be used inside a guild.", ephemeral=True
				)
				return
			target_ids = {interaction.guild.id}

		results: list[str] = []
		for guild_id in target_ids:
			guild_obj = discord.Object(id=guild_id)
			try:
				self.bot.tree.copy_global_to(guild=guild_obj)
				commands_synced = await self.bot.tree.sync(guild=guild_obj)
				results.append(f"{guild_id}: {len(commands_synced)} commands")
			except Exception as exc:  # pragma: no cover - defensive logging
				logging.exception("Failed to sync commands for guild %s", guild_id)
				results.append(f"{guild_id}: failed ({exc})")

		await interaction.followup.send(
			"Command sync results:\n" + "\n".join(results), ephemeral=True
		)


async def setup(bot: commands.Bot) -> None:
	await bot.add_cog(AdminCommandsCog(bot))
