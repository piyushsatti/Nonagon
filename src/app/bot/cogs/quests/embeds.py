from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

import discord

from app.bot.utils.quest_embeds import (
    QuestEmbedData,
    QuestEmbedRoster,
    build_quest_embed as build_quest_embed_from_data,
)
from app.domain.models.EntityIDModel import UserID
from app.domain.models.QuestModel import PlayerStatus, Quest

UserDisplayResolver = Callable[[int, UserID], str]


def quest_to_embed_data(
    quest: Quest,
    guild: Optional[discord.Guild],
    *,
    lookup_user_display: UserDisplayResolver,
    referee_display: Optional[str] = None,
    approved_by_display: Optional[str] = None,
    last_updated_at: Optional[datetime] = None,
) -> QuestEmbedData:
    roster_selected: list[str] = []
    roster_pending: list[str] = []

    for signup in quest.signups:
        label = (
            f"{lookup_user_display(quest.guild_id, signup.user_id)} — {str(signup.character_id)}"
        )
        if signup.status is PlayerStatus.SELECTED:
            roster_selected.append(label)
        else:
            roster_pending.append(label)

    roster = QuestEmbedRoster(selected=roster_selected, pending=roster_pending)

    referee_label = referee_display
    if referee_label is None:
        referee_label = lookup_user_display(quest.guild_id, quest.referee_id)

    data = QuestEmbedData(
        quest_id=str(quest.quest_id),
        title=quest.title,
        description=quest.description,
        status=quest.status,
        starting_at=quest.starting_at,
        duration=quest.duration,
        referee_display=referee_label,
        roster=roster,
        image_url=quest.image_url,
        last_updated_at=last_updated_at or datetime.now(timezone.utc),
        approved_by_display=approved_by_display,
    )
    return data


def build_quest_embed(
    quest: Quest,
    guild: Optional[discord.Guild],
    *,
    lookup_user_display: UserDisplayResolver,
    referee_display: Optional[str] = None,
    approved_by_display: Optional[str] = None,
    last_updated_at: Optional[datetime] = None,
) -> discord.Embed:
    data = quest_to_embed_data(
        quest,
        guild,
        lookup_user_display=lookup_user_display,
        referee_display=referee_display,
        approved_by_display=approved_by_display,
        last_updated_at=last_updated_at,
    )
    return build_quest_embed_from_data(data)


def build_nudge_embed(
    quest: Quest,
    member: discord.Member,
    jump_url: str,
    *,
    bumped_at: datetime,
) -> discord.Embed:
    quest_title = quest.title or str(quest.quest_id)
    embed = discord.Embed(
        title=f"Quest Nudge: {quest_title}",
        description=(
            f"{member.mention} bumped this quest.\n"
            f"[View announcement]({jump_url})"
        ),
        color=discord.Color.gold(),
        timestamp=bumped_at,
    )

    if quest.starting_at:
        start_ts = quest.starting_at
        if start_ts.tzinfo is None or start_ts.tzinfo.utcoffset(start_ts) is None:
            start_ts = start_ts.replace(tzinfo=timezone.utc)
        embed.add_field(
            name="Start Time",
            value=f"<t:{int(start_ts.timestamp())}:F>",
            inline=False,
        )

    embed.set_footer(text=f"Quest ID: {quest.quest_id}")
    return embed
