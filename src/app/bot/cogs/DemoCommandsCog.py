from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from app.bot import database
from app.bot.config import DEMO_RESET_ENABLED
from app.bot.utils.log_stream import send_demo_log


class DemoCommandsCog(commands.Cog):
    """Utility commands for operating the public demo."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _reset_guild(self, guild: discord.Guild) -> None:
        db_name = str(guild.id)
        logging.info("Resetting demo database for guild %s", guild.id)
        database.delete_db(db_name)
        self.bot.guild_data.pop(guild.id, None)
        await self.bot.load_or_create_guild_cache(guild)

    def _next_seq(self, guild: discord.Guild, prefix: str) -> int:
        db = self.bot.guild_data[guild.id]["db"]
        doc = db["counters"].find_one_and_update(
            {"_id": prefix}, {"$inc": {"seq": 1}}, upsert=True, return_document=True
        )
        return int(doc["seq"]) if doc and "seq" in doc else 1

    def _seed_demo(self, guild: discord.Guild) -> None:
        db = self.bot.guild_data[guild.id]["db"]

        # Seed character for guild owner (or first non-bot member)
        owner = guild.owner or next((m for m in guild.members if not m.bot), None)
        if owner:
            char_seq = self._next_seq(guild, "CHAR")
            db["characters"].update_one(
                {"guild_id": guild.id, "character_id.number": char_seq},
                {
                    "$set": {
                        "guild_id": guild.id,
                        "character_id": {"prefix": "CHAR", "number": char_seq},
                        "owner_id": {"prefix": "USER", "number": owner.id},
                        "name": f"Demo Hero #{char_seq:04d}",
                        "ddb_link": "https://example.com/character",
                        "character_thread_link": "https://example.com/thread",
                        "token_link": "https://example.com/token.png",
                        "art_link": "https://example.com/art.png",
                    }
                },
                upsert=True,
            )

        # Seed a quest 24h from now
        import datetime as _dt

        q_seq = self._next_seq(guild, "QUES")
        starts = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=24)
        db["quests"].update_one(
            {"guild_id": guild.id, "quest_id.number": q_seq},
            {
                "$set": {
                    "guild_id": guild.id,
                    "quest_id": {"prefix": "QUES", "number": q_seq},
                    "referee_id": {"prefix": "USER", "number": (owner.id if owner else 0)},
                    "channel_id": str(getattr(guild.system_channel, "id", 0)),
                    "message_id": "0",
                    "raw": "# Demo Quest\nA simple seed quest.",
                    "title": "Demo Quest",
                    "description": "A seeded quest for the demo",
                    "starting_at": starts,
                    "duration": 7200,
                    "status": "ANNOUNCED",
                }
            },
            upsert=True,
        )

    @app_commands.command(name="demo_about", description="Overview of the Nonagon demo experience.")
    async def demo_about(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Welcome to the Nonagon Demo",
            description="Explore quest scheduling, signups, and engagement stats using slash commands.",
            colour=discord.Color.blurple(),
        )
        embed.add_field(
            name="Core Commands",
            value="`/createquest`, `/joinquest`, `/character_add`, `/stats`, `/leaderboard`",
            inline=False,
        )
        embed.add_field(
            name="Demo Tips",
            value=(
                "Use `/demo_reset` (admins) to wipe data, then `/demo_about` to brief new explorers.\n"
                "After ending a quest, encourage players to file summaries!"
            ),
            inline=False,
        )
        embed.set_footer(text="Telemetry updates every ~15 seconds via MongoDB flush loop.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="demo_reset", description="Reset demo data for this guild.")
    async def demo_reset(self, interaction: discord.Interaction) -> None:
        if not DEMO_RESET_ENABLED:
            await interaction.response.send_message(
                "Demo reset is disabled on this deployment.", ephemeral=True
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command must be used inside a guild.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await self._reset_guild(interaction.guild)
        # Seed sample content
        self._seed_demo(interaction.guild)

        await send_demo_log(
            self.bot,
            interaction.guild,
            f"Demo data reset by {interaction.user.mention}",
        )

        await interaction.followup.send(
            "Demo data has been reset and seeded with a sample quest and character.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(DemoCommandsCog(bot))
