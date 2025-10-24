from __future__ import annotations

import pytest

from app.domain.models.EntityIDModel import (
	CharacterID,
	POSTAL_BODY_PATTERN,
	QuestID,
	SummaryID,
	UserID,
)


def _is_postal(value: str) -> bool:
	return bool(POSTAL_BODY_PATTERN.fullmatch(value))


def test_generate_produces_postal_bodies() -> None:
	quest_id = QuestID.generate()
	assert quest_id.value.startswith(QuestID.prefix)
	assert _is_postal(quest_id.body)


@pytest.mark.parametrize(
	"cls",
	[UserID, CharacterID, QuestID, SummaryID],
)
def test_numeric_body_remains_supported(cls) -> None:
	legacy = cls.from_body("123456")
	assert legacy.body == "123456"
	assert legacy.value.startswith(cls.prefix)


@pytest.mark.parametrize(
	"raw",
	["QUESabc123", "QUES1A2B3C", "QUES!!!!"],
)
def test_invalid_bodies_raise(raw: str) -> None:
	with pytest.raises(ValueError):
		QuestID.parse(raw)


def test_prefix_enforced() -> None:
	with pytest.raises(ValueError):
		QuestID.parse(str(CharacterID.generate()))


def test_string_representation_round_trip() -> None:
	summary_id = SummaryID.generate()
	parsed = SummaryID.parse(str(summary_id))
	assert parsed == summary_id
	assert _is_postal(parsed.body)
