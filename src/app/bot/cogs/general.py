from __future__ import annotations

from typing import Protocol, runtime_checkable

import discord
from discord import app_commands
from discord.ext import commands


@runtime_checkable
class SupportsBotStatus(Protocol):
    """Protocol covering the attributes used by the general commands cog."""

    @property
    def latency(self) -> float: ...

    def is_ready(self) -> bool: ...

    @property
    def user(self) -> object | None: ...


class GeneralCog(commands.Cog):
    """General utility commands for quickly checking bot health."""

    def __init__(self, bot: SupportsBotStatus) -> None:
        """Attach the Discord bot instance used for health checks."""
        super().__init__()
        self.bot = bot

    def build_latency_message(self) -> str:
        """Return a human-readable websocket latency string."""
        latency_ms = round(self.bot.latency * 1000)
        return f"Pong! Websocket latency: {latency_ms} ms"

    def build_status_embed(self) -> discord.Embed:
        """Construct an embed describing latency and ready state."""
        latency_ms = round(self.bot.latency * 1000)
        try:
            ready = self.bot.is_ready()
        except Exception:  # pragma: no cover - defensive
            ready = False
        colour = discord.Color.green() if ready else discord.Color.orange()
        description = "Basic health information for the Nonagon Discord bot."
        embed = discord.Embed(
            title="Bot status", description=description, colour=colour
        )
        embed.add_field(name="Websocket latency", value=f"{latency_ms} ms", inline=True)
        embed.add_field(
            name="Ready state",
            value="Ready ✅" if ready else "Starting ⏳",
            inline=True,
        )
        user = getattr(self.bot, "user", None)
        if user is not None:
            embed.set_footer(text=f"Logged in as {user}")
        return embed

    @commands.command(name="ping")
    async def command_ping_prefix(self, ctx: commands.Context[commands.Bot]) -> None:
        """Prefix command to check websocket latency."""

        await ctx.reply(self.build_latency_message())

    @app_commands.command(
        name="ping",
        description="Check that the Nonagon bot is responding and view latency.",
    )
    async def command_ping_slash(self, interaction: discord.Interaction) -> None:
        """Slash command variant of ping that responds ephemerally."""

        await interaction.response.send_message(
            self.build_latency_message(),
            ephemeral=True,
        )

    @commands.command(name="pingstatus")
    async def command_pingstatus_prefix(
        self, ctx: commands.Context[commands.Bot]
    ) -> None:
        """Prefix command returning a richer status embed."""

        await ctx.reply(embed=self.build_status_embed())

    @app_commands.command(
        name="pingstatus",
        description="Show the bot's readiness state and websocket latency.",
    )
    async def command_pingstatus_slash(self, interaction: discord.Interaction) -> None:
        """Slash command that provides a richer status embed."""

        await interaction.response.send_message(
            embed=self.build_status_embed(),
            ephemeral=True,
        )
