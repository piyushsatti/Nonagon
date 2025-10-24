from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.bot.utils.quest_embeds import QuestEmbedData, QuestEmbedRoster, build_quest_embed
from app.domain.models.QuestModel import QuestStatus


def test_build_quest_embed_uses_emoji_headers() -> None:
	data = QuestEmbedData(
		quest_id="QUES0001",
		title="Rescue Mission",
		description="Save the villagers from goblins.",
		status="ANNOUNCED",
		starting_at=datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc),
		duration=timedelta(hours=3, minutes=30),
		referee_display="@DM",
		roster=QuestEmbedRoster(selected=["Player1"], pending=["Player2"]),
		image_url=None,
	)

	embed = build_quest_embed(data)

	assert [field.name for field in embed.fields] == [
		"🎯 Quest",
		"⏰ Time",
		"🧑‍🤝‍🧑 Players",
	]


def test_footer_shows_active_indicator() -> None:
	last_updated = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
	data = QuestEmbedData(
		quest_id="QUES0001",
		status=QuestStatus.ANNOUNCED,
		referee_display="@DM",
		last_updated_at=last_updated,
		approved_by_display="@DM",
	)

	embed = build_quest_embed(data)

	epoch = int(last_updated.timestamp())
	assert embed.footer.text == f"Quest ID: QUES0001 • 🟢 Active • Approved by @DM - Updated <t:{epoch}:R>"


def test_footer_shows_closed_indicator() -> None:
	last_updated = datetime(2030, 1, 2, 15, 0, tzinfo=timezone.utc)
	data = QuestEmbedData(
		quest_id="QUES0001",
		status=QuestStatus.SIGNUP_CLOSED,
		referee_display="@DM",
		last_updated_at=last_updated,
		approved_by_display="@DM",
	)

	embed = build_quest_embed(data)

	epoch = int(last_updated.timestamp())
	assert embed.footer.text == f"Quest ID: QUES0001 • 🔴 Closed • Approved by @DM - Updated <t:{epoch}:R>"
