from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import pytest

from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID
from app.domain.models.summary.IGTModel import InGameTime, parse_in_game_time
from app.domain.models.summary.SummaryAttachmentModel import SummaryAttachment
from app.domain.models.summary.SummaryModel import (
    AdventureSummary,
    AdventureSummaryIssue,
    AutoSummaryStatus,
    ContentFormatQuality,
    SummaryKind,
    SummaryParticipant,
    validate_adventure_summary,
)


def make_summary(**overrides: Any) -> AdventureSummary:
    base = AdventureSummary(
        summary_id=SummaryID(1),
        quest_id=QuestID(1),
        kind=SummaryKind.PLAYER,
        author_user_id=UserID(1),
        author_discord_id="1001",
        author_character_id=CharacterID(1),
        players=[SummaryParticipant(user_id=UserID(1), display_name="Astra")],
        discord_guild_id="guild-1",
        discord_channel_id="channel-42",
        summary_message_ids=["msg-1", "msg-1", "msg-2"],
        short_summary_md="A brave tale",
        content_md="## Summary\nIt begins.\n## Players\n- Astra",
        raw_markdown="## Summary\nIt begins.\n## Players\n- Astra\n## Region\nSouth\n## In-Game Time\nPlanting W2",
        related_links=["https://example.com/log"],
        auto_summary_status=AutoSummaryStatus.NONE,
    )
    return replace(base, **overrides) if overrides else base


def test_content_forms_text_only() -> None:
    summary = make_summary(attachments=[])
    assert summary.content_md


def test_content_forms_attachments_only() -> None:
    attachment = SummaryAttachment(kind="image", url="https://img.example/test.png")
    summary = make_summary(content_md="", attachments=[attachment])
    assert summary.attachments == [attachment]


def test_content_forms_mixed_media() -> None:
    attachment = SummaryAttachment(kind="file", url="https://cdn.example/log.pdf")
    summary = make_summary(attachments=[attachment])
    assert summary.content_md and summary.attachments


def test_player_summary_requires_participants() -> None:
    with pytest.raises(ValueError):
        make_summary(players=[])


def test_in_game_time_parser_best_effort() -> None:
    parsed = parse_in_game_time("Planting W2")
    assert parsed.season == "Planting"
    assert parsed.week == 2


def test_provenance_dedupes_message_ids() -> None:
    summary = make_summary(summary_message_ids=["msg-1", "msg-1", "msg-2", "msg-1"])
    assert summary.summary_message_ids == ["msg-1", "msg-2"]


def test_auto_summary_lifecycle_transitions() -> None:
    base = make_summary()
    pending = replace(base, auto_summary_status=AutoSummaryStatus.PENDING)
    assert pending.auto_summary_status is AutoSummaryStatus.PENDING

    completed = replace(
        base,
        auto_summary_status=AutoSummaryStatus.COMPLETE,
        auto_summary_md="### Recap\nDone",
        auto_summary_created_at=datetime.now(timezone.utc),
    )
    assert completed.auto_summary_status is AutoSummaryStatus.COMPLETE
    assert completed.auto_summary_md is not None
    assert completed.auto_summary_created_at is not None

    with pytest.raises(ValueError):
        make_summary(auto_summary_md="text-only")


def test_format_quality_classification() -> None:
    strict = make_summary()
    assert strict.format_quality is ContentFormatQuality.STRICT

    lax_raw = "## Recap\nNotes\n## Cast\n- Astra\n## Area\nSouth"
    lax = make_summary(raw_markdown=lax_raw)
    assert lax.format_quality is ContentFormatQuality.LAX

    broken = make_summary(
        raw_markdown="Just vibes",
        content_md="",
        attachments=[SummaryAttachment(kind="link", url="https://example.com")],
    )
    assert broken.format_quality is ContentFormatQuality.BROKEN


def test_validation_helper_reports_issues() -> None:
    summary = make_summary()
    summary.players.clear()
    summary.attachments.clear()
    summary.content_md = ""
    summary.summary_message_ids.clear()
    issues = validate_adventure_summary(summary)
    codes = {issue.code for issue in issues}
    assert codes == {"SUMMARY0001", "SUMMARY0002", "SUMMARY0004"}
    assert all(isinstance(issue, AdventureSummaryIssue) for issue in issues)


def test_in_game_time_week_must_be_positive() -> None:
    invalid_igt = InGameTime(raw="Planting W0", season="Planting", week=0)
    with pytest.raises(ValueError):
        make_summary(igt=invalid_igt)
