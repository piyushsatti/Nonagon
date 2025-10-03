from __future__ import annotations

import re
from dataclasses import dataclass

from app.bot.ingestion import DiscordMessageKey, QuestRecord
from app.bot.ingestion.summaries_pipeline import AdventureSummaryRecord
from app.infra.mongo.quest_records_repo import QuestRecordsRepository
from app.infra.mongo.summary_records_repo import SummaryRecordsRepository

_QUEST_ID_RE = re.compile(r"^QUES\d+$", re.IGNORECASE)
_SUMMARY_ID_RE = re.compile(r"^SUMM\d+$", re.IGNORECASE)
_MESSAGE_LINK_RE = re.compile(
    r"https://discord(?:app)?\.com/channels/(?P<guild_id>\d+)/(?P<channel_id>\d+)/(?P<message_id>\d+)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class QuestLookupResult:
    quest: QuestRecord
    summaries: list[AdventureSummaryRecord]


@dataclass(slots=True)
class SummaryLookupResult:
    summary: AdventureSummaryRecord
    quest: QuestRecord | None
    related_summaries: list[AdventureSummaryRecord]


class QuestLookupService:
    """Fetch quest and summary records for Discord command lookups."""

    def __init__(
        self,
        *,
        quest_repo: QuestRecordsRepository,
        summary_repo: SummaryRecordsRepository,
    ) -> None:
        self._quests = quest_repo
        self._summaries = summary_repo

    async def fetch_quest(self, identifier: str) -> QuestLookupResult | None:
        """Return quest metadata and linked summaries.

        The identifier can be a quest ID (``QUES1234``) or a Discord message link.
        """

        normalized = identifier.strip()
        if not normalized:
            return None

        quest = await self._resolve_quest_identifier(normalized)
        if quest is None:
            return None

        summaries = await self._summaries.list_by_quest_id(quest.quest_id)
        return QuestLookupResult(quest=quest, summaries=summaries)

    async def fetch_summary(self, identifier: str) -> SummaryLookupResult | None:
        """Return a summary record plus its parent quest and sibling summaries."""

        normalized = identifier.strip()
        if not normalized:
            return None

        summary = await self._resolve_summary_identifier(normalized)
        if summary is None:
            return None

        quest = await self._resolve_summary_parent(summary)
        related: list[AdventureSummaryRecord] = []
        if summary.quest_id:
            related = await self._summaries.list_by_quest_id(summary.quest_id)
        return SummaryLookupResult(
            summary=summary, quest=quest, related_summaries=related
        )

    async def _resolve_quest_identifier(self, identifier: str) -> QuestRecord | None:
        if _QUEST_ID_RE.fullmatch(identifier):
            quest = await self._quests.get_by_quest_id(identifier.upper())
            if quest is not None:
                return quest

        key = self._parse_message_link(identifier)
        if key is not None:
            quest = await self._quests.get_by_discord_key(key)
            if quest is not None:
                return quest

        return None

    async def _resolve_summary_identifier(
        self, identifier: str
    ) -> AdventureSummaryRecord | None:
        if _SUMMARY_ID_RE.fullmatch(identifier):
            summary = await self._summaries.get_by_summary_id(identifier.upper())
            if summary is not None:
                return summary

        key = self._parse_message_link(identifier)
        if key is not None:
            summary = await self._summaries.get_by_discord_message(key)
            if summary is not None:
                return summary

        return None

    async def _resolve_summary_parent(
        self, summary: AdventureSummaryRecord
    ) -> QuestRecord | None:
        if summary.quest_id:
            quest = await self._quests.get_by_quest_id(summary.quest_id)
            if quest is not None:
                return quest

        if summary.parent_message_id:
            key = DiscordMessageKey.from_ids(
                summary.discord_guild_id,
                summary.discord_channel_id,
                summary.parent_message_id,
            )
            quest = await self._quests.get_by_discord_key(key)
            if quest is not None:
                return quest

        return None

    def _parse_message_link(self, value: str) -> DiscordMessageKey | None:
        match = _MESSAGE_LINK_RE.search(value)
        if not match:
            return None
        return DiscordMessageKey(
            guild_id=match.group("guild_id"),
            channel_id=match.group("channel_id"),
            message_id=match.group("message_id"),
        )

    async def warm_cache(self) -> None:  # pragma: no cover - reserved for future use
        """Hook for future prefetching or caching."""
        return

    async def refresh(self) -> None:  # pragma: no cover - reserved for parity
        """Hook for future refresh logic to keep API symmetry."""
        return


__all__ = [
    "QuestLookupService",
    "QuestLookupResult",
    "SummaryLookupResult",
]
