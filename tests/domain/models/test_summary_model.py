import pytest
from datetime import datetime, timedelta
from app.domain.models.SummaryModel import QuestSummary, SummaryKind
from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID


def make_summary(now: datetime) -> QuestSummary:
    return QuestSummary(
        summary_id=SummaryID(1),
        kind=SummaryKind.PLAYER,
        author_id=UserID(1),
        character_id=CharacterID(1),
        quest_id=QuestID(1),
        raw="# content",
        title="A tale",
        description="Desc",
        created_on=now,
        players=(UserID(1),),
        characters=(CharacterID(1),),
    )


def test_validate_summary_happy(now):
    s = make_summary(now)
    s.validate_summary()  # should not raise


def test_validate_summary_requires_players_and_characters(now):
    s = make_summary(now)
    s.players = []
    with pytest.raises(ValueError):
        s.validate_summary()

    s = make_summary(now)
    s.characters = []
    with pytest.raises(ValueError):
        s.validate_summary()


def test_last_edited_cannot_precede_created(now):
    s = make_summary(now)
    s.last_edited_at = now - timedelta(days=1)
    with pytest.raises(ValueError):
        s.validate_summary()