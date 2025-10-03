from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import discord

from app.bot.cogs.general import GeneralCog
from app.bot.ingestion import QuestRecord
from app.bot.ingestion.pipeline import LinkedQuestRecord
from app.bot.ingestion.summaries_pipeline import (
    AdventureSummaryRecord,
    SummaryAttachmentRecord,
    SummaryParticipantRecord,
)
from app.bot.services.guild_logging import GuildLoggingService
from app.bot.services.quest_lookup import QuestLookupService
from app.domain.models.summary.SummaryModel import (
    AutoSummaryStatus,
    SummaryKind,
    SummaryStatus,
)


class StubQuestRepo:
    async def get_by_quest_id(self, quest_id: str) -> None:  # pragma: no cover - stub
        return None

    async def get_by_discord_key(self, key: Any) -> None:  # pragma: no cover - stub
        return None


class StubSummaryRepo:
    async def list_by_quest_id(
        self, quest_id: str
    ) -> list[AdventureSummaryRecord]:  # pragma: no cover - stub
        return []

    async def get_by_summary_id(
        self, summary_id: str
    ) -> AdventureSummaryRecord | None:  # pragma: no cover - stub
        return None

    async def get_by_discord_message(
        self, key: Any
    ) -> AdventureSummaryRecord | None:  # pragma: no cover - stub
        return None


def _make_lookup_service() -> QuestLookupService:
    return QuestLookupService(  # type: ignore[arg-type]
        quest_repo=StubQuestRepo(),
        summary_repo=StubSummaryRepo(),
    )


class DummyBot:
    def __init__(self, latency: float, ready: bool = True) -> None:
        self._latency = latency
        self._ready = ready
        self._user = SimpleNamespace(name="TestBot", id=123456789012345678)

    @property
    def latency(self) -> float:
        return self._latency

    def is_ready(self) -> bool:
        return self._ready

    @property
    def user(self) -> SimpleNamespace:
        return self._user

    def __str__(self) -> str:  # pragma: no cover - best effort repr
        return f"{self.user.name}#{self.user.id}"


class FaultyReadyBot(DummyBot):
    def __init__(self, latency: float) -> None:
        super().__init__(latency)

    def is_ready(self) -> bool:  # type: ignore[override]
        raise RuntimeError("ready state unavailable")


def test_latency_message_formats_latency_ms() -> None:
    bot = DummyBot(latency=0.321)
    cog = GeneralCog(
        bot,
        logging_service=GuildLoggingService(),
        lookup_service=_make_lookup_service(),
    )

    message = cog.build_latency_message()

    assert message.startswith("Pong!")
    assert "321" in message  # latency formatted in milliseconds


def test_status_embed_reflects_ready_state() -> None:
    bot = DummyBot(latency=0.045, ready=True)
    cog = GeneralCog(
        bot,
        logging_service=GuildLoggingService(),
        lookup_service=_make_lookup_service(),
    )

    embed = cog.build_status_embed()

    assert embed.title == "Bot status"
    assert embed.fields[0].name == "Websocket latency"
    assert embed.fields[0].value == "45 ms"
    assert embed.fields[1].value == "Ready ✅"
    assert embed.colour == discord.Color.green()


def test_status_embed_handles_not_ready_and_exceptions() -> None:
    bot = DummyBot(latency=0.1, ready=False)
    cog = GeneralCog(
        bot,
        logging_service=GuildLoggingService(),
        lookup_service=_make_lookup_service(),
    )
    embed = cog.build_status_embed()
    assert embed.fields[1].value == "Starting ⏳"
    assert embed.colour == discord.Color.orange()

    faulty_bot = FaultyReadyBot(latency=0.2)
    faulty_cog = GeneralCog(
        faulty_bot,
        logging_service=GuildLoggingService(),
        lookup_service=_make_lookup_service(),
    )
    embed_faulty = faulty_cog.build_status_embed()
    assert embed_faulty.fields[1].value == "Starting ⏳"


def test_build_quest_lookup_embed_includes_core_fields() -> None:
    bot = DummyBot(latency=0.1)
    cog = GeneralCog(
        bot,
        logging_service=GuildLoggingService(),
        lookup_service=_make_lookup_service(),
    )

    now = datetime.now(timezone.utc)
    quest = QuestRecord.model_validate(
        {
            "quest_id": "QUES1234",
            "title": "Expedition to the Shattered Coast",
            "description_md": "A daring jaunt beyond the barrier.",
            "region_name": "Shattered Coast",
            "region_hex": "#112233",
            "tags": ["Exploration", "Roleplay"],
            "starts_at_utc": now + timedelta(days=1),
            "ends_at_utc": now + timedelta(days=1, hours=4),
            "duration_minutes": 240,
            "my_table_url": "https://example.com/table",
            "linked_quests": [],
            "event_url": "https://example.com/event",
            "image_url": "https://example.com/banner.png",
            "referee_discord_id": "1234567890",
            "referee_user_id": None,
            "discord_guild_id": "555",
            "discord_channel_id": "666",
            "discord_message_id": "777",
            "status": "ACTIVE",
            "raw": "raw quest text",
            "created_at": now,
            "updated_at": now,
        }
    )

    summary = AdventureSummaryRecord.model_validate(
        {
            "summary_id": "SUMM9876",
            "quest_id": "QUES1234",
            "kind": SummaryKind.PLAYER,
            "author_user_id": None,
            "author_discord_id": "2345",
            "author_character_id": None,
            "in_character": True,
            "title": "Victory at the Coast",
            "short_summary_md": "A concise recap of the adventure.",
            "content_md": "Long form content",
            "attachments": [],
            "region_text": None,
            "igt": None,
            "dm_discord_id": None,
            "players": [
                SummaryParticipantRecord(discord_id="2345", display_name="Ranger")
            ],
            "related_links": ["https://example.com/report"],
            "discord_guild_id": "555",
            "discord_channel_id": "888",
            "parent_message_id": None,
            "summary_message_ids": ["999"],
            "auto_summary_status": AutoSummaryStatus.NONE,
            "auto_summary_md": None,
            "auto_summary_model": None,
            "auto_summary_version": None,
            "auto_summary_created_at": None,
            "format_quality": "LAX",
            "status": SummaryStatus.PUBLISHED,
            "created_at": now,
            "updated_at": now,
            "raw_markdown": "**Summary**",
        }
    )

    embed = cog.build_quest_lookup_embed(quest, [summary])

    assert embed.title == quest.title
    assert any(
        field.name == "Quest ID" and field.value == quest.quest_id
        for field in embed.fields
    )
    field_values = [str(field.value) for field in embed.fields]
    assert any("SUMM9876" in value for value in field_values)


def test_build_summary_lookup_embed_handles_siblings() -> None:
    bot = DummyBot(latency=0.1)
    cog = GeneralCog(
        bot,
        logging_service=GuildLoggingService(),
        lookup_service=_make_lookup_service(),
    )

    now = datetime.now(timezone.utc)
    quest = QuestRecord.model_validate(
        {
            "quest_id": "QUES2024",
            "title": "Siege of Dawnfall",
            "description_md": "Battle for the city.",
            "region_name": "Dawnfall",
            "region_hex": "#445566",
            "tags": ["Combat"],
            "starts_at_utc": now,
            "ends_at_utc": now + timedelta(hours=3),
            "duration_minutes": 180,
            "my_table_url": "https://example.com/table2",
            "linked_quests": [
                LinkedQuestRecord(guild_id="555", channel_id="123", message_id="456")
            ],
            "event_url": "https://example.com/event2",
            "image_url": None,
            "referee_discord_id": "7890",
            "referee_user_id": None,
            "discord_guild_id": "555",
            "discord_channel_id": "123",
            "discord_message_id": "456",
            "status": "ACTIVE",
            "raw": "raw",
            "created_at": now,
            "updated_at": now,
        }
    )

    summary_primary = AdventureSummaryRecord.model_validate(
        {
            "summary_id": "SUMM2001",
            "quest_id": "QUES2024",
            "kind": SummaryKind.PLAYER,
            "author_user_id": None,
            "author_discord_id": "9999",
            "author_character_id": None,
            "in_character": True,
            "title": "Siege Recap",
            "short_summary_md": "Quick recap",
            "content_md": "Detailed recap",
            "attachments": [
                SummaryAttachmentRecord(kind="image", url="https://example.com/img.png")
            ],
            "region_text": None,
            "igt": None,
            "dm_discord_id": None,
            "players": [
                SummaryParticipantRecord(discord_id="9999", display_name="Paladin")
            ],
            "related_links": [],
            "discord_guild_id": "555",
            "discord_channel_id": "123",
            "parent_message_id": "456",
            "summary_message_ids": ["777"],
            "auto_summary_status": AutoSummaryStatus.NONE,
            "auto_summary_md": None,
            "auto_summary_model": None,
            "auto_summary_version": None,
            "auto_summary_created_at": None,
            "format_quality": "LAX",
            "status": SummaryStatus.PUBLISHED,
            "created_at": now,
            "updated_at": now,
            "raw_markdown": "**Summary**",
        }
    )

    summary_sibling = AdventureSummaryRecord.model_validate(
        {
            "summary_id": "SUMM2002",
            "quest_id": "QUES2024",
            "kind": SummaryKind.REFEREE,
            "author_user_id": None,
            "author_discord_id": "8888",
            "author_character_id": None,
            "in_character": False,
            "title": "GM Notes",
            "short_summary_md": "GM recap",
            "content_md": "GM view",
            "attachments": [],
            "region_text": None,
            "igt": None,
            "dm_discord_id": "8888",
            "players": [],
            "related_links": [],
            "discord_guild_id": "555",
            "discord_channel_id": "123",
            "parent_message_id": "456",
            "summary_message_ids": ["778"],
            "auto_summary_status": AutoSummaryStatus.NONE,
            "auto_summary_md": None,
            "auto_summary_model": None,
            "auto_summary_version": None,
            "auto_summary_created_at": None,
            "format_quality": "LAX",
            "status": SummaryStatus.PUBLISHED,
            "created_at": now,
            "updated_at": now,
            "raw_markdown": "**GM**",
        }
    )

    embed = cog.build_summary_lookup_embed(
        summary_primary,
        quest,
        [summary_primary, summary_sibling],
    )

    assert embed.title == summary_primary.title
    assert any(
        field.name == "Summary ID" and field.value == summary_primary.summary_id
        for field in embed.fields
    )
    sibling_fields = [
        (field.name, str(field.value))
        for field in embed.fields
        if field.name and field.name.startswith("Other")
    ]
    assert any("SUMM2002" in value for _, value in sibling_fields)
