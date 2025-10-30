from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
# inspect not required here

import discord
from discord.ext import commands

from app.bot.database import db_client
from app.bot.utils.logging import get_logger
from app.bot.utils.sync import sync_guilds


logger = get_logger(__name__)

CRITICAL_PERMISSIONS = [
    "send_messages",
    "embed_links",
    "read_message_history",
    "manage_messages",
    "attach_files",
    "use_application_commands",
]


class Diagnostics(commands.Cog):
    """Operational diagnostics for the Nonagon bot."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.started_at = datetime.now(timezone.utc)

    # --- helpers -----------------------------------------------------------------

    @staticmethod
    def _make_embed(title: str, description: str | None = None) -> discord.Embed:
        embed = discord.Embed(
            title=title, description=description, colour=discord.Color.blurple()
        )
        embed.set_footer(text="Diagnostics")
        return embed

    async def _send_failure(
        self, interaction: discord.Interaction, command: str, error: Exception
    ) -> None:
        logger.exception("Diagnostics command %s failed: %s", command, error)
        embed = self._make_embed("Diagnostics Error", f"{command}: {error}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _send_failure_for_ctx(
        self, ctx: commands.Context, command: str, error: Exception
    ) -> None:
        logger.exception("Diagnostics command %s failed: %s", command, error)
        embed = self._make_embed("Diagnostics Error", f"{command}: {error}")
        try:
            await ctx.send(embed=embed)
        except Exception:
            await ctx.send(f"Diagnostics Error: {command}: {error}")

    @staticmethod
    def _human_duration(delta: timedelta) -> str:
        total_seconds = int(delta.total_seconds())
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts: List[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")
        return " ".join(parts)

    async def _mongo_status(self) -> Tuple[bool, str]:
        def _ping() -> Tuple[bool, str]:
            try:
                db_client.admin.command("ping")
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("MongoDB ping failed: %s", exc)
                return False, str(exc)
            return True, "OK"

        return await asyncio.to_thread(_ping)

    # --- commands ----------------------------------------------------------------

    @commands.command(name="botstatus")
    @commands.is_owner()
    async def botstatus_cmd(self, ctx: commands.Context) -> None:
        """Owner-only: show runtime diagnostics (prefix command)."""
        try:
            now = datetime.now(timezone.utc)
            uptime = self._human_duration(now - self.started_at)
            mongo_ok, mongo_msg = await self._mongo_status()
            shard_id = getattr(self.bot, "shard_id", None)
            latency_ms = round(self.bot.latency * 1000, 2)

            embed = self._make_embed("Bot Status")
            embed.add_field(name="Uptime", value=uptime, inline=True)
            embed.add_field(name="Latency", value=f"{latency_ms} ms", inline=True)
            embed.add_field(
                name="Shard",
                value=str(shard_id) if shard_id is not None else "N/A",
                inline=True,
            )
            embed.add_field(
                name="MongoDB",
                value=("✅ " + mongo_msg) if mongo_ok else ("⚠️ " + mongo_msg),
                inline=True,
            )
            embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)

            await ctx.send(embed=embed)
        except Exception as exc:
            await self._send_failure_for_ctx(ctx, "botstatus", exc)

    @commands.command(name="loadedcogs")
    @commands.is_owner()
    async def loadedcogs_cmd(self, ctx: commands.Context) -> None:
        """Owner-only: list loaded extensions (prefix command)."""
        try:
            cogs = sorted(self.bot.extensions.keys())
            description = "\n".join(cogs) if cogs else "No extensions loaded."
            embed = self._make_embed("Loaded Cogs", description)
            await ctx.send(embed=embed)
        except Exception as exc:
            await self._send_failure_for_ctx(ctx, "loadedcogs", exc)

    @commands.command(name="commandcheck")
    @commands.is_owner()
    async def commandcheck_cmd(self, ctx: commands.Context) -> None:
        """Owner-only: inspect registered application commands (prefix command)."""
        try:
            lines: List[str] = []
            for command in self.bot.tree.get_commands():
                callback = getattr(command, "callback", None)
                status = "✅" if callable(callback) else "⚠️"
                lines.append(f"{status} /{command.qualified_name}")

            embed = self._make_embed(
                "Command Audit",
                "\n".join(lines) if lines else "No commands registered.",
            )
            await ctx.send(embed=embed)
        except Exception as exc:
            await self._send_failure_for_ctx(ctx, "commandcheck", exc)

    @commands.command(name="permscheck")
    @commands.is_owner()
    async def permscheck_cmd(
        self, ctx: commands.Context, channel: discord.abc.GuildChannel
    ) -> None:
        """Owner-only: check bot permissions for a channel (prefix command)."""
        try:
            guild = channel.guild
            member = guild.me
            if member is None and self.bot.user is not None:
                member = guild.get_member(self.bot.user.id)
            if member is None and self.bot.user is not None:
                try:
                    member = await guild.fetch_member(self.bot.user.id)
                except Exception:
                    member = None

            if member is None:
                raise RuntimeError("Unable to resolve bot membership in guild.")

            perms = channel.permissions_for(member)
            missing = [
                perm for perm in CRITICAL_PERMISSIONS if not getattr(perms, perm, False)
            ]

            embed = self._make_embed("Permission Check")
            embed.add_field(name="Channel", value=getattr(channel, "mention", str(channel)), inline=False)
            embed.add_field(
                name="Allowed",
                value=", ".join(
                    sorted(p for p in CRITICAL_PERMISSIONS if p not in missing)
                )
                or "None",
                inline=False,
            )
            embed.add_field(
                name="Missing",
                value=", ".join(missing) if missing else "None",
                inline=False,
            )

            await ctx.send(embed=embed)
        except Exception as exc:
            await self._send_failure_for_ctx(ctx, "permscheck", exc)

    @commands.command(name="cacheprobe")
    @commands.is_owner()
    async def cacheprobe_cmd(self, ctx: commands.Context) -> None:
        """Owner-only: inspect guild and member cache state (prefix command)."""
        try:
            guild_cache = getattr(self.bot, "guild_data", {})
            cached_guilds = len(guild_cache)
            cached_users = sum(
                len(entry.get("users", {})) for entry in guild_cache.values()
            )

            mismatches: List[str] = []
            for guild_id, entry in guild_cache.items():

                def _count_docs() -> int | None:
                    try:
                        match = {
                            "$or": [
                                {"guild_id": guild_id},
                                {"guild_id": {"$exists": False}},
                            ]
                        }
                        return entry["db"].users.count_documents(match)
                    except Exception as exc:  # pragma: no cover - defensive logging
                        logger.exception(
                            "Failed counting users for guild %s: %s", guild_id, exc
                        )
                        return None

                remote_count = await asyncio.to_thread(_count_docs)
                local_count = len(entry.get("users", {}))
                if remote_count is not None and remote_count != local_count:
                    mismatches.append(
                        f"Guild {guild_id}: cache={local_count}, mongo={remote_count}"
                    )

            embed = self._make_embed("Cache Probe")
            embed.add_field(
                name="Connected Guilds", value=str(len(self.bot.guilds)), inline=True
            )
            embed.add_field(name="Cached Guilds", value=str(cached_guilds), inline=True)
            embed.add_field(name="Cached Users", value=str(cached_users), inline=True)
            if mismatches:
                embed.add_field(
                    name="Mismatches", value="\n".join(mismatches), inline=False
                )
            else:
                embed.add_field(name="Mismatches", value="None", inline=False)

            await ctx.send(embed=embed)
        except Exception as exc:
            await self._send_failure_for_ctx(ctx, "cacheprobe", exc)

    @commands.command(name="eventlog")
    @commands.is_owner()
    async def eventlog_cmd(self, ctx: commands.Context, latest: int = 10) -> None:
        """Owner-only: show recent events captured by the bot (prefix command)."""
        try:
            buffer = getattr(self.bot, "event_buffer", None)
            if not buffer:
                embed = self._make_embed("Event Log", "Event buffer not implemented.")
                await ctx.send(embed=embed)
                return

            recent = list(buffer)[-latest:]
            lines = [str(item) for item in recent]
            embed = self._make_embed(
                "Event Log", "\n".join(lines) if lines else "No events recorded."
            )
            await ctx.send(embed=embed)
        except Exception as exc:
            await self._send_failure_for_ctx(ctx, "eventlog", exc)

    @commands.command(name="syncdiagnostic")
    @commands.is_owner()
    async def syncdiagnostic_cmd(self, ctx: commands.Context, all_guilds: bool = False) -> None:
        """Owner-only: run a command-sync audit (prefix command).

    Reuses centralized sync helper to perform a per-guild sync and report results.
        Invoke as `n!syncdiagnostic` (current guild) or `n!syncdiagnostic True` (all guilds).
        """
        try:
            # use centralized helper
            if all_guilds:
                target_ids = {guild.id for guild in self.bot.guilds}
                if not target_ids:
                    await ctx.send("Bot is not connected to any guilds; nothing to check.")
                    return
            else:
                if ctx.guild is None:
                    await ctx.send("This diagnostic must be run inside a guild unless `True` is passed to run across all guilds.")
                    return
                target_ids = {ctx.guild.id}

            await ctx.send("Running command sync diagnostic… this will perform a command sync for target guild(s).")
            results = await sync_guilds(self.bot, target_ids)
            lines = [str(r) for r in (results or [])]
            embed = self._make_embed("Command Sync Diagnostic", "\n".join(lines) if lines else "No results.")
            await ctx.send(embed=embed)
        except Exception as exc:
            await self._send_failure_for_ctx(ctx, "syncdiagnostic", exc)

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync_cmd(self, ctx: commands.Context) -> None:
        """Owner-only: sync application commands for the current guild (prefix)."""
        try:
            if ctx.guild is None:
                await ctx.send("This command must be run inside a guild.")
                return

            await ctx.send("Running command sync for this guild…")
            results = await sync_guilds(self.bot, {ctx.guild.id})
            embed = self._make_embed("Command Sync (guild)", "\n".join(results) if results else "No results.")
            await ctx.send(embed=embed)
        except Exception as exc:
            await self._send_failure_for_ctx(ctx, "sync", exc)

    @commands.command(name="syncall")
    @commands.is_owner()
    async def syncall_cmd(self, ctx: commands.Context) -> None:
        """Owner-only: sync application commands across all guilds (prefix)."""
        try:
            target_ids = {g.id for g in self.bot.guilds}
            if not target_ids:
                await ctx.send("Bot is not connected to any guilds; nothing to sync.")
                return

            await ctx.send("Running command sync across all guilds… this may take a while.")
            results = await sync_guilds(self.bot, target_ids)
            embed = self._make_embed("Command Sync (all guilds)", "\n".join(results) if results else "No results.")
            await ctx.send(embed=embed)
        except Exception as exc:
            await self._send_failure_for_ctx(ctx, "syncall", exc)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Diagnostics(bot))
