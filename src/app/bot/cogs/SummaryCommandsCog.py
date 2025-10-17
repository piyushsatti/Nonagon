from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID
from app.domain.models.SummaryModel import QuestSummary, SummaryKind


class SummaryCommandsCog(commands.Cog):
    """Skeleton commands for quest summaries (validate + preview via DM)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="summary_add", description="Draft a quest summary and preview via DM.")
    @app_commands.describe(
        kind="Summary type",
        character_id="Character identifier (CHARxxxx)",
        quest_id="Quest identifier (QUESxxxx)",
        title="Summary title",
        description="Short description",
    )
    @app_commands.choices(
        kind=[
            app_commands.Choice(name="Player", value="PLAYER"),
            app_commands.Choice(name="Referee", value="REFEREE"),
        ]
    )
    async def summary_add(
        self,
        interaction: discord.Interaction,
        kind: app_commands.Choice[str],
        character_id: str,
        quest_id: str,
        title: str,
        description: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None:
            await interaction.followup.send(
                "This command must be used in a guild.", ephemeral=True
            )
            return

        author = interaction.user
        if not isinstance(author, discord.Member):
            await interaction.followup.send(
                "Only guild members can file summaries.", ephemeral=True
            )
            return

        try:
            s = QuestSummary(
                summary_id=SummaryID(number=1),  # placeholder; not persisted yet
                kind=SummaryKind(kind.value),
                author_id=UserID(number=author.id),
                character_id=CharacterID.parse(character_id.upper()),
                quest_id=QuestID.parse(quest_id.upper()),
                guild_id=interaction.guild.id,
                raw=f"# {title}\n{description}",
                title=title,
                description=description,
                created_on=datetime.now(timezone.utc),
                players=[UserID(number=author.id)],
                characters=[CharacterID.parse(character_id.upper())],
            )
            s.validate_summary()
        except Exception as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        try:
            dm = await author.create_dm()
            embed = discord.Embed(
                title=f"Summary Preview — {title}", description=description, colour=discord.Color.teal()
            )
            embed.add_field(name="Kind", value=kind.value, inline=True)
            embed.add_field(name="Quest", value=quest_id.upper(), inline=True)
            embed.add_field(name="Character", value=character_id.upper(), inline=True)
            await dm.send(embed=embed)
        except Exception:
            # Ignore DM failures silently; user may have DMs closed
            pass

        await interaction.followup.send(
            "Summary validated. A DM preview was sent if possible (no data has been stored).",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SummaryCommandsCog(bot))
