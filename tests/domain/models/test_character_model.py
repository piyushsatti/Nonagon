import pytest
from datetime import datetime, timedelta
from app.domain.models.CharacterModel import Character, CharacterRole
from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID


def make_character(now: datetime) -> Character:
    return Character(
        owner_id=UserID(1),
        character_id="CHAR0001",  # field is str in current model
        name="Aela",
        ddb_link="https://ddb.example/1",
        character_thread_link="https://forum/char1",
        token_link="https://img/token1.png",
        art_link="https://img/art1.png",
        status=CharacterRole.ACTIVE,
        created_at=now,
        last_played_at=now,
        description="",
        notes="",
    )


def test_activation_and_change_attributes(now):
    c = make_character(now)
    assert c.is_active() is True
    c.deactivate()
    assert c.is_active() is False
    c.activate()
    assert c.is_active() is True

    c.change_attributes(name="Aela Storm", description="New desc")
    assert c.name == "Aela Storm"
    assert c.description == "New desc"


def test_update_last_played_rejects_earlier_than_created(now):
    c = make_character(now)
    earlier = now - timedelta(days=1)
    with pytest.raises(ValueError):
        c.update_last_played(earlier)


def test_link_lists(now):
    c = make_character(now)
    other = CharacterID(2)
    q = QuestID(3)
    s = SummaryID(4)

    c.add_played_with(other)
    c.add_played_in(q)
    c.add_mentioned_in(s)

    assert other in c.played_with
    assert q in c.played_in
    assert s in c.mentioned_in

    c.remove_played_with(other)
    c.remove_played_in(q)
    c.remove_mentioned_in(s)

    assert other not in c.played_with
    assert q not in c.played_in
    assert s not in c.mentioned_in


def test_validate_character_minimal(now):
    c = make_character(now)
    c.validate_character()  # should not raise

