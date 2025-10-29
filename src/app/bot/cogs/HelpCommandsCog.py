from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


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
                "Popular: `/quest create`, `/summary create`, `/joinquest`, `/character create`, `/stats`, `/leaderboard`.\n"
                "Visit the demo dashboard at `/demo` (web)."
            ),
            colour=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)



async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommandsCog(bot))
