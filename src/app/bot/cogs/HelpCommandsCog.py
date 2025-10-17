from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.config import BOT_CLIENT_ID


class HelpCommandsCog(commands.Cog):
    """Basic help and invite commands for demo onboarding."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="Show quickstart and useful links.")
    async def help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Nonagon — Quickstart",
            description=(
                "Use slash commands to schedule quests, join signups, and view stats.\n\n"
                "Popular: `/createquest`, `/joinquest`, `/character_add`, `/stats`, `/leaderboard`.\n"
                "Visit the demo dashboard at `/demo` (web)."
            ),
            colour=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="invite", description="Get an OAuth2 invite link for the bot.")
    async def invite(self, interaction: discord.Interaction) -> None:
        if not BOT_CLIENT_ID:
            await interaction.response.send_message(
                "Invite unavailable: `BOT_CLIENT_ID` is not configured.", ephemeral=True
            )
            return

        scopes = "applications.commands%20bot"
        perms = 268463104  # send messages, manage messages (adjust as needed)
        url = f"https://discord.com/api/oauth2/authorize?client_id={BOT_CLIENT_ID}&permissions={perms}&scope={scopes}"
        await interaction.response.send_message(
            f"Invite me with this link:\n{url}", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommandsCog(bot))

