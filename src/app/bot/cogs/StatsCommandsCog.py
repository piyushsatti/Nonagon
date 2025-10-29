from __future__ import annotations

import logging
from datetime import timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.domain.models.UserModel import User


class StatsCommandsCog(commands.Cog):
    """Slash commands for engagement statistics."""

    LEADERBOARD_FIELDS = {
        "messages": ("messages_count_total", "Messages Sent"),
        "reactions_given": ("reactions_given", "Reactions Given"),
        "reactions_received": ("reactions_received", "Reactions Received"),
        "voice": ("voice_total_time_spent", "Voice Time (hrs)"),
    }

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

    @app_commands.command(name="stats", description="View your engagement stats.")
    async def stats(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Only guild members can view stats.", ephemeral=True
            )
            return

        try:
            user = await self._get_cached_user(member)
        except RuntimeError as exc:
            logging.exception("Failed to resolve user for stats: %s", exc)
            await interaction.response.send_message(
                "Internal error resolving your profile; please try again later.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"Stats for {member.display_name}",
            colour=discord.Color.gold(),
        )
        embed.add_field(
            name="Messages", value=str(user.messages_count_total), inline=True
        )
        embed.add_field(
            name="Reactions Given", value=str(user.reactions_given), inline=True
        )
        embed.add_field(
            name="Reactions Received", value=str(user.reactions_received), inline=True
        )
        embed.add_field(
            name="Voice Time (hrs)",
            value=f"{user.voice_total_time_spent:.2f}",
            inline=True,
        )
        if user.last_active_at:
            last_active = user.last_active_at
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            else:
                last_active = last_active.astimezone(timezone.utc)
            epoch = int(last_active.timestamp())
            embed.set_footer(text=f"Last active: <t:{epoch}:R>")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="leaderboard", description="View engagement leaderboards."
    )
    @app_commands.describe(metric="Metric to rank users by")
    @app_commands.choices(
        metric=[
            app_commands.Choice(name="Messages", value="messages"),
            app_commands.Choice(name="Reactions Given", value="reactions_given"),
            app_commands.Choice(name="Reactions Received", value="reactions_received"),
            app_commands.Choice(name="Voice Time", value="voice"),
        ]
    )
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        metric: app_commands.Choice[str],
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        await self._ensure_guild_cache(interaction.guild)
        guild_entry = self.bot.guild_data[interaction.guild.id]
        db = guild_entry["db"]

        field, label = self.LEADERBOARD_FIELDS[metric.value]

        cursor = (
            db["users"]
            .find(
                {"guild_id": interaction.guild.id, field: {"$gt": 0}},
                {"_id": 0, "discord_id": 1, field: 1},
            )
            .sort(field, -1)
            .limit(10)
        )
        rows = list(cursor)

        if not rows:
            await interaction.response.send_message(
                f"No data available for {metric.name} yet.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"{interaction.guild.name} — {label} Leaderboard",
            colour=discord.Color.purple(),
        )

        for idx, row in enumerate(rows, start=1):
            discord_id = row.get("discord_id")
            member = (
                interaction.guild.get_member(int(discord_id))
                if discord_id is not None
                else None
            )
            display = (
                member.display_name if member else f"User {discord_id}" or "Unknown"
            )
            value = row.get(field, 0)
            if field == "voice_total_time_spent":
                value = f"{float(value):.2f} hrs"
            embed.add_field(name=f"#{idx} {display}", value=str(value), inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="nudges", description="Enable or disable DM reminders.")
    @app_commands.describe(state="Choose whether to receive DM reminders from the bot")
    @app_commands.choices(
        state=[
            app_commands.Choice(name="Enable", value="enable"),
            app_commands.Choice(name="Disable", value="disable"),
        ]
    )
    async def nudges(
        self,
        interaction: discord.Interaction,
        state: app_commands.Choice[str],
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Only guild members can update reminders.", ephemeral=True
            )
            return

        try:
            user = await self._get_cached_user(member)
        except RuntimeError as exc:
            logging.exception("Failed to resolve user for nudges: %s", exc)
            await interaction.response.send_message(
                "Internal error resolving your profile; please try again later.",
                ephemeral=True,
            )
            return

        enable = state.value == "enable"
        user.dm_opt_in = enable

        await self.bot.dirty_data.put((interaction.guild.id, member.id))
        await interaction.response.send_message(
            f"DM reminders {'enabled' if enable else 'disabled'}.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCommandsCog(bot))
