from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.bot.ingestion import ParseError
from app.bot.ingestion.summaries_pipeline import (
    ParsedAdventureSummary,
    ParsedParticipant,
    SummaryParseError,
)
from app.bot.services import adventure_summary_ingestion as summary_module
from app.bot.services import quest_ingestion as quest_module
from app.bot.services.adventure_summary_ingestion import (
    AdventureSummaryIngestionService,
)
from app.bot.services.quest_ingestion import QuestIngestionService
from app.infra.mongo.ingest_failures_repo import IngestFailureRepository
from app.infra.mongo.quest_records_repo import QuestRecordsRepository
from app.infra.mongo.summary_records_repo import SummaryRecordsRepository


class RecordingFailureRepo:
    def __init__(self) -> None:
        self.records: list[Any] = []

    async def record_failure(self, record: Any) -> None:  # pragma: no cover - helper
        self.records.append(record)


class StubQuestRepo:
    async def get_by_discord_message(
        self, key: Any
    ) -> None:  # pragma: no cover - helper
        return None


class StubSummaryRepo:
    def __init__(self) -> None:  # pragma: no cover - helper
        self.records: list[Any] = []

    async def get_by_discord_message(
        self, key: Any
    ) -> None:  # pragma: no cover - helper
        return None

    async def upsert(self, record: Any) -> Any:  # pragma: no cover - helper
        self.records.append(record)
        return record


class RecordingLoggingService:
    def __init__(self) -> None:  # pragma: no cover - helper
        self.events: list[dict[str, Any]] = []

    async def log_event(
        self,
        guild_id: int,
        *,
        title: str,
        description: str | None = None,
        fields: list[tuple[str, str]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:  # pragma: no cover - helper
        self.events.append(
            {
                "guild_id": guild_id,
                "title": title,
                "description": description,
                "fields": fields or [],
                "extra": extra or {},
            }
        )


class StubIdService:
    async def next_quest_id(self) -> str:  # pragma: no cover - helper
        return "QUES9999"

    async def next_summary_id(self) -> str:  # pragma: no cover - helper
        return "SUMM9999"

    async def ensure_user_id(self, discord_id: str) -> str:  # pragma: no cover - helper
        return f"USER-{discord_id}"


def _make_message(channel_id: int) -> SimpleNamespace:
    guild = SimpleNamespace(id=987654321)
    channel = SimpleNamespace(id=channel_id)
    author = SimpleNamespace(
        id=123456789,
        bot=False,
        display_name="Chronicler",
        name="Chronicler",
        roles=[],
    )
    return SimpleNamespace(
        content="# Test",
        guild=guild,
        channel=channel,
        author=author,
        attachments=[],
        reference=None,
        created_at=datetime.now(timezone.utc),
        edited_at=None,
        id=999000111,
    )


@pytest.mark.asyncio
async def test_quest_ingestion_records_failure_on_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure_repo = RecordingFailureRepo()

    def fake_parse_message(**_: Any) -> None:  # pragma: no cover - helper
        raise ParseError(["Missing title"])

    monkeypatch.setattr(quest_module, "parse_message", fake_parse_message)

    service = QuestIngestionService(
        repo=cast(QuestRecordsRepository, StubQuestRepo()),
        id_service=StubIdService(),
        quest_channel_id=42,
        referee_role_id=None,
        logging_service=None,
        failure_repo=cast(IngestFailureRepository, failure_repo),
    )

    message = _make_message(42)

    await service.ingest_new_message(cast(Any, message))

    assert len(failure_repo.records) == 1
    record = failure_repo.records[0]
    assert record.kind == "quest"
    assert record.reason == "parse_error"
    assert record.errors == ["Missing title"]
    assert record.raw_content == message.content


@pytest.mark.asyncio
async def test_summary_ingestion_records_failure_on_missing_quest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure_repo = RecordingFailureRepo()

    parsed = ParsedAdventureSummary(
        quest_id=None,
        guild_id="987654321",
        channel_id="77",
        message_id="88",
        author_discord_id="123456789",
        author_display_name="Chronicler",
        parent_message_id=None,
        title="Test Summary",
        short_summary_md="Short",
        content_md="Content",
        raw_markdown="Content",
        region_text=None,
        igt_text=None,
        dm_discord_id=None,
        players=[ParsedParticipant(discord_id="123456789", display_name="Chronicler")],
        related_links=[],
        kind_hint=None,
        in_character=True,
        created_at=datetime.now(timezone.utc),
        edited_at=None,
        quest_message_ref=None,
    )

    def fake_parse_message(
        **_: Any,
    ) -> ParsedAdventureSummary:  # pragma: no cover - helper
        return parsed

    monkeypatch.setattr(summary_module, "parse_message", fake_parse_message)

    summary_repo = StubSummaryRepo()
    logging_service = RecordingLoggingService()

    service = AdventureSummaryIngestionService(
        repo=cast(SummaryRecordsRepository, summary_repo),
        id_service=StubIdService(),
        summary_channel_id=84,
        referee_role_id=None,
        logging_service=logging_service,  # type: ignore[arg-type]
        quest_repo=None,
        failure_repo=cast(IngestFailureRepository, failure_repo),
    )

    message = _make_message(84)

    await service.ingest_new_message(cast(Any, message))

    assert len(summary_repo.records) == 1
    stored = summary_repo.records[0]
    assert stored.summary_id == "SUMM9999"
    assert stored.quest_id is None
    assert stored.raw_markdown == parsed.raw_markdown
    assert stored.summary_message_ids == [parsed.message_id]

    assert len(logging_service.events) == 1
    event = logging_service.events[0]
    assert event["guild_id"] == message.guild.id
    assert event["title"] == "Summary stored (quest unresolved)"
    assert ("Summary ID", stored.summary_id) in event["fields"]

    assert len(failure_repo.records) == 1
    record = failure_repo.records[0]
    assert record.kind == "summary"
    assert record.reason == "missing_quest_reference"
    assert record.metadata == {"quest_id": None, "quest_link": None}


@pytest.mark.asyncio
async def test_summary_ingestion_records_failure_on_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure_repo = RecordingFailureRepo()

    def fake_parse_message(**_: Any) -> None:  # pragma: no cover - helper
        raise SummaryParseError(["Missing quest reference"])

    monkeypatch.setattr(summary_module, "parse_message", fake_parse_message)

    service = AdventureSummaryIngestionService(
        repo=cast(SummaryRecordsRepository, StubSummaryRepo()),
        id_service=StubIdService(),
        summary_channel_id=84,
        referee_role_id=None,
        logging_service=None,
        quest_repo=None,
        failure_repo=cast(IngestFailureRepository, failure_repo),
    )

    message = _make_message(84)

    await service.ingest_new_message(cast(Any, message))

    assert len(failure_repo.records) == 1
    record = failure_repo.records[0]
    assert record.kind == "summary"
    assert record.reason == "parse_error"
    assert record.errors == ["Missing quest reference"]
