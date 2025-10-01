from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.discord_bot.ingestion.summaries_pipeline import (
    SummaryParseError,
    map_parsed_to_domain,
    map_summary_to_record,
    parse_message,
    validate,
)
from app.domain.models.summary.SummaryAttachmentModel import SummaryAttachment
from app.domain.models.summary.SummaryModel import SummaryKind


def _base_message() -> str:
    return """# Adventure Summary: Shadows in the North
**Quest ID:** QUES0001
**Summary Type:** Player
**Region:** Emerald Vale
**In-Game Time:** Planting W2
**DM:** <@2222>

## Summary
We ventured into the woods and discovered a hidden shrine.

## Players
- <@1111> Astra
- <@3333> Borek

## Links
https://example.com/log
"""


def test_parse_and_map_summary_round_trip() -> None:
    raw = _base_message()

    parsed = parse_message(
        raw=raw,
        author_discord_id="1111",
        author_display_name="Astra",
        guild_id=555,
        channel_id=777,
        message_id=999,
        created_at=datetime(2025, 9, 30, tzinfo=timezone.utc),
        edited_at=None,
        parent_message_id=None,
    )

    attachments = [
        SummaryAttachment(kind="image", url="https://cdn.example.com/image.png")
    ]

    domain_summary = map_parsed_to_domain(
        parsed,
        summary_id="SUMM0002",
        author_user_id="USER0004",
        attachments=attachments,
        summary_kind=SummaryKind.PLAYER,
    )

    validate(domain_summary)

    record = map_summary_to_record(domain_summary)

    assert record.summary_id == "SUMM0002"
    assert record.quest_id == "QUES0001"
    assert record.kind == SummaryKind.PLAYER
    assert record.discord_channel_id == "777"
    assert record.summary_message_ids == ["999"]
    assert record.attachments[0].kind == "image"
    assert record.related_links == ["https://example.com/log"]


def test_parse_message_requires_quest_id() -> None:
    raw = """# Adventure Summary
Missing metadata block

## Summary
Just vibes.
"""
    with pytest.raises(SummaryParseError):
        parse_message(
            raw=raw,
            author_discord_id="1111",
            author_display_name="Astra",
            guild_id=1,
            channel_id=2,
            message_id=3,
            created_at=datetime.now(timezone.utc),
            edited_at=None,
            parent_message_id=None,
        )


def test_parse_without_players_defaults_author() -> None:
    raw = """# Adventure Summary: Solo Tale
**Quest ID:** QUES0009

## Summary
Alone, I braved the darkness.
"""
    parsed = parse_message(
        raw=raw,
        author_discord_id="5555",
        author_display_name="Soloist",
        guild_id=99,
        channel_id=88,
        message_id=77,
        created_at=datetime.now(timezone.utc),
        edited_at=None,
        parent_message_id=None,
    )

    domain_summary = map_parsed_to_domain(
        parsed,
        summary_id="SUMM0042",
        author_user_id=None,
        attachments=[],
        summary_kind=SummaryKind.PLAYER,
    )

    validate(domain_summary)
    assert len(domain_summary.players) == 1
    participant = domain_summary.players[0]
    assert participant.discord_id == "5555"
    assert participant.display_name == "Soloist"
