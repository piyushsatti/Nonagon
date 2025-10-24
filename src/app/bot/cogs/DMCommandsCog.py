from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.domain.models.UserModel import User


class DMCommandsCog(commands.Cog):
	"""Handles direct-message interactions for registration and help."""

	def __init__(self, bot: commands.Bot) -> None:
		self.bot = bot

	async def _get_or_create_user(self, user: discord.User) -> User:
		guilds = [g for g in self.bot.guilds if g.get_member(user.id)]
		if not guilds:
			raise ValueError("You must be a member of at least one guild the bot is in.")

		primary_guild = guilds[0]
		listener: Optional[commands.Cog] = self.bot.get_cog("ListnerCog")
		if listener is None:
			raise RuntimeError("Listener cog not loaded; cannot resolve users.")

		ensure_method = getattr(listener, "_ensure_cached_user", None)
		if ensure_method is None:
			raise RuntimeError("Listener cog missing _ensure_cached_user helper.")

		member = primary_guild.get_member(user.id)
		if member is None:
			member = await primary_guild.fetch_member(user.id)

		return await ensure_method(member)  # type: ignore[misc]

	@app_commands.command(name="register", description="Set up your demo profile via DM.")
	async def register(self, interaction: discord.Interaction) -> None:
		if interaction.guild is not None:
			await interaction.response.send_message(
				"Please DM me to run `/register`.", ephemeral=True
			)
			return

		await interaction.response.defer(ephemeral=True, thinking=True)
		try:
			user = await self._get_or_create_user(interaction.user)
		except ValueError as exc:
			await interaction.followup.send(str(exc), ephemeral=True)
			return
		except Exception as exc:  # pragma: no cover - DM edge cases
			logging.exception("Failed to register user via DM: %s", exc)
			await interaction.followup.send(
				"Something went wrong while setting up your profile. Please try again later.",
				ephemeral=True,
			)
			return

		message = (
			"Your demo profile is active!\n\n"
			"Available commands:\n"
			"• `/character_add` – create a character\n"
			"• `/createquest` – schedule a quest (referees)\n"
			"• `/stats` – view engagement metrics\n"
			"• `/nudges enable|disable` – control reminders\n"
		)
		await interaction.followup.send(message, ephemeral=True)


async def setup(bot: commands.Bot):
	await bot.add_cog(DMCommandsCog(bot))
