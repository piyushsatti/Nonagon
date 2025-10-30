from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.services import guild_settings_store


class GuildCommandsCog(commands.Cog):
    """Legacy guild command group retained for convenience."""

    guild = app_commands.Group(
        name="guild", description="Inspect Nonagon state for this guild."
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @guild.command(name="help", description="Discover guild utilities.")
    @app_commands.guild_only()
    async def guild_help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Nonagon Guild Commands",
            description=(
                "Configuration has moved to `/setup`. Try `/setup help` for the full list. "
                "This legacy group still offers quick stats."
            ),
            colour=discord.Colour.blurple(),
        )
        embed.add_field(
            name="/guild stats",
            value="Show quick stats about this server and cached guild data.",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
            role_set = {guild.get_role(rid) for rid in allowed_role_ids}
            role_set = {role for role in role_set if role is not None}
            for member in guild.members:
                if any(role in member.roles for role in role_set):
                    allowed_role_members += 1

        server_tagged_count = 0
        if server_tag_role_id:
            role = guild.get_role(server_tag_role_id)
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
                name="Allowed role coverage",
                value=str(allowed_role_members),
                inline=False,
            )
        if server_tag_role_id:
            embed.add_field(
                name="Server-tagged members",
                value=str(server_tagged_count),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @staticmethod
    def _coerce_int(raw: Optional[object]) -> Optional[int]:
        try:
            if raw is None:
                return None
            return int(raw)
        except (TypeError, ValueError):
            return None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GuildCommandsCog(bot))
