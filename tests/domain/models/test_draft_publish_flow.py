from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.models.quest.DraftQuestModel import DraftQuest, build_discord_time_tokens
from app.domain.models.EntityIDModel import QuestID, UserID
from app.domain.models.quest.QuestModel import (
    Quest,
    QuestFormatQuality,
    map_draft_to_quest,
)
from app.domain.models.quest.TagPolicyModel import TagPolicy


def test_tag_policy_normalization_and_cap():
    policy = TagPolicy(
        max_tags=2, normalization="kebab", aliases={"gw-hunt": "guild-hunt"}
    )
    tags = ["  GW Hunt  ", "Lore Drop", "GW hunt"]

    normalized = policy.normalize(tags)

    assert normalized == ["guild-hunt", "lore-drop"]


def test_draft_refresh_preview_generates_tokens():
    start = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    draft = DraftQuest(
        draft_id="DRAFT0001",
        referee_discord_id="1234",
        title="Test Quest",
        description_md="# Quest",
        region_text="Pawluck Valley",
        start_input_utc=start,
        duration_input_minutes=150,
        my_table_url="https://example.com/table",
    )

    draft.refresh_preview()

    epoch = int(start.timestamp())
    assert draft.discord_time_tokens == build_discord_time_tokens(start)
    assert draft.hammertime_url is not None
    assert draft.hammertime_url.endswith(f"#{epoch}")
    assert draft.duration_text == "2h 30m"


def test_strict_quest_requires_event_metadata():
    start = datetime.now(timezone.utc) + timedelta(days=1)
    quest = Quest(
        quest_id=QuestID(1),
        referee_id=UserID(1),
        channel_id="chan",
        message_id="msg",
        raw="# raw",
        title="Quest Title",
        description="Desc",
        region_text="Songnest",
        tags_accepted=["tag"],
        starts_at_utc=start,
        duration_minutes=120,
        my_table_url="https://example.com/table",
        format_quality=QuestFormatQuality.STRICT,
        posted_by_bot=True,
    )

    with pytest.raises(ValueError):
        quest.validate_quest()

    quest.event_id = "123"
    quest.event_url = "https://discord.com/events/123"
    quest.validate_quest()


def test_linked_messages_validation():
    start = datetime.now(timezone.utc) + timedelta(days=1)
    quest = Quest(
        quest_id=QuestID(2),
        referee_id=UserID(2),
        channel_id="chan",
        message_id="msg",
        raw="# raw",
        title="Quest",
        description="Desc",
        region_text="Songnest",
        tags_accepted=["tag"],
        starts_at_utc=start,
        duration_minutes=60,
        my_table_url="https://example.com/table",
        linked_messages=[{"guild_id": "1", "channel_id": "2", "message_id": "3"}],
    )

    quest.validate_quest()  # should not raise

    quest.linked_messages = [{"guild_id": "1", "channel_id": "", "message_id": "3"}]
    with pytest.raises(ValueError):
        quest.validate_quest()


def test_map_draft_to_quest_populates_publish_fields():
    start = datetime.now(timezone.utc) + timedelta(days=7)
    draft = DraftQuest(
        draft_id="DRAFT0002",
        referee_discord_id="6789",
        title="Dungeon Run",
        description_md="# Dungeon Run",
        region_text="V9, Viceroc",
        tags_input=["Action", "Story"],
        start_input_utc=start,
        duration_input_minutes=180,
        my_table_url="https://example.com/table",
        linked_messages=[{"guild_id": "1", "channel_id": "2", "message_id": "3"}],
    )

    policy = TagPolicy()
    quest = map_draft_to_quest(
        draft,
        quest_id=QuestID(3),
        message_ids={"guild_id": "10", "channel_id": "11", "message_id": "12"},
        event={"event_id": "evt-1", "event_url": "https://discord.com/events/evt-1"},
        tag_policy=policy,
        referee_id=UserID(3),
    )

    assert quest.format_quality is QuestFormatQuality.STRICT
    assert quest.posted_by_bot is True
    assert quest.event_id == "evt-1"
    assert quest.tags_raw == ["Action", "Story"]
    assert len(quest.discord_time_tokens) >= 1
    quest.validate_quest()
