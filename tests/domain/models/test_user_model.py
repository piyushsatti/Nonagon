
# tests/test_user_model.py
import math
import pytest
from datetime import datetime
from app.domain.models.UserModel import User, Player, Referee
from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID


def test_user_id_roundtrip():
    uid = UserID(42)
    s = str(uid)
    assert UserID.parse(s) == uid


def test_defaults_and_roles(base_user: User):
    assert base_user.is_member is True
    assert base_user.is_player is False
    assert base_user.is_referee is False
    base_user.validate_user()


def test_enable_player_sets_profile(base_user: User):
    base_user.enable_player()
    assert base_user.is_player is True
    assert base_user.player is not None


def test_enable_referee_sets_profile(base_user: User):
    base_user.enable_referee()
    assert base_user.is_referee is True
    assert base_user.referee is not None


def test_is_character_owner_when_player(player_user: User):
    c = CharacterID(7)
    player_user.player.add_character(c)
    assert player_user.is_character_owner(c) is True


def test_disable_player_blocked_if_referee(referee_user: User):
    with pytest.raises(ValueError):
        referee_user.disable_player()


def test_update_joined_at_allows_initial_set(base_user: User):
    joined = datetime(2029, 1, 1)
    base_user.update_joined_at(joined)
    assert base_user.joined_at == joined


def test_counters_and_voice_time(base_user: User):
    base_user.increment_messages_count(2)
    base_user.increment_reactions_given(3)
    base_user.increment_reactions_received(4)
    base_user.add_voice_time_spent(7200)  # 2 hours

    assert base_user.messages_count_total == 2
    assert base_user.reactions_given == 3
    assert base_user.reactions_received == 4
    assert math.isclose(base_user.voice_total_time_spent, 2.0)


def test_player_and_referee_validations():
    p = Player()
    p.add_character(CharacterID(1))
    p.add_quest_applied(QuestID(2))
    p.add_quest_played(QuestID(3))
    p.increment_summaries_written(SummaryID(4))
    p.add_played_with_character(CharacterID(99), seconds=3600)
    p.validate_player()  # should not raise

    r = Referee()
    r.add_quest_hosted(QuestID(10))
    r.increment_summaries_written(SummaryID(11))
    r.add_collabed_with(UserID(5), seconds=7200)
    r.add_hosted_for(UserID(6))
    r.validate_referee()  # should not raise
