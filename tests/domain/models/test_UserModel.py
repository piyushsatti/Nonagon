import pytest
from datetime import datetime, timedelta
from typing import Any

from app.domain.models.UserModel import User, Role, PlayerProfile, RefereeProfile

"""
What these tests cover (and why they're “junior friendly”)

Safe defaults: New User starts as MEMBER, with clean counters and maps—prevents NoneType mistakes.

Role helpers: ensure_role and enable_* are idempotent (calling twice is safe), and profile objects aren’t replaced accidentally.

Factories: from_discord_member works even if some fields are missing; from_dict ignores unknown keys (defensive loading).

Serialization: to_dict() returns a plain dict, including nested profiles when enabled—useful for storage/logging.
"""

# ─────────────────────────────────────────────────────────────
# Helpers / Stubs
# ─────────────────────────────────────────────────────────────
class StubDMChannel:
  def __init__(self, id_: int): self.id = id_

class StubDiscordMember:
  """Tiny stand in for a discord Member object."""
  def __init__(self, member_id: int, joined_at: datetime | None = None, dm_channel_id: int | None = None):
    self.id = member_id
    self.joined_at = joined_at
    self.dm_channel = StubDMChannel(dm_channel_id) if dm_channel_id is not None else None


# ─────────────────────────────────────────────────────────────
# Basic construction & defaults
# ─────────────────────────────────────────────────────────────
def test_user_defaults_include_member_role():
  u = User()
  assert u.roles == [Role.MEMBER], "New users should start with the MEMBER role"
  assert u.player is None and u.referee is None, "No profiles are attached by default"


def test_user_default_counters_and_maps():
  u = User()
  # simple counters at zero
  assert u.messages_count_total == 0
  assert u.reactions_given == 0
  assert u.reactions_received == 0
  # dict fields default to empty dicts
  assert isinstance(u.messages_count_by_category, dict) and not u.messages_count_by_category
  assert isinstance(u.voice_time_by_channel, dict) and not u.voice_time_by_channel


# ─────────────────────────────────────────────────────────────
# Role helpers (idempotent & create profiles)
# ─────────────────────────────────────────────────────────────
def test_ensure_role_is_idempotent():
  u = User()
  u.ensure_role(Role.PLAYER)
  u.ensure_role(Role.PLAYER)  # should not duplicate
  assert u.roles.count(Role.PLAYER) == 1
  assert Role.MEMBER in u.roles  # original role remains


def test_enable_player_creates_profile_and_role_once():
  u = User()
  u.enable_player()
  assert Role.PLAYER in u.roles
  assert isinstance(u.player, PlayerProfile)
  # calling again should NOT replace/reset the profile
  profile_id = id(u.player)
  u.enable_player()
  assert id(u.player) == profile_id


def test_enable_referee_creates_profile_and_role_once():
  u = User()
  u.enable_referee()
  assert Role.REFEREE in u.roles
  assert isinstance(u.referee, RefereeProfile)
  # calling again should NOT replace/reset the profile
  profile_id = id(u.referee)
  u.enable_referee()
  assert id(u.referee) == profile_id


# ─────────────────────────────────────────────────────────────
# Factories
# ─────────────────────────────────────────────────────────────
def test_from_discord_member_populates_core_fields():
  m = StubDiscordMember(member_id=12345, joined_at=datetime.utcnow() - timedelta(days=1), dm_channel_id=999)
  u = User.from_discord_member(m)

  # ids
  assert u.user_id == str(12345)
  assert u.discord_id == 12345
  assert u.dm_channel_id == 999

  # timestamps: joined_at should come from member or default to "now"
  assert isinstance(u.joined_at, datetime)
  assert isinstance(u.last_active_at, datetime)


def test_from_discord_member_works_when_dm_channel_missing():
  m = StubDiscordMember(member_id=98765, joined_at=None, dm_channel_id=None)
  u = User.from_discord_member(m)
  assert u.dm_channel_id is None
  assert u.user_id == str(98765)


def test_from_dict_filters_unknown_fields():
  data: dict[str, Any] = {
      "user_id": "abc",
      "discord_id": 111,
      "roles": [Role.MEMBER],      # valid
      "made_up_field": "ignore",   # should be ignored
      "player": None,
      "referee": None,
  }
  u = User.from_dict(data)
  assert u.user_id == "abc"
  assert u.discord_id == 111
  assert not hasattr(u, "made_up_field")


# ─────────────────────────────────────────────────────────────
# Serialization
# ─────────────────────────────────────────────────────────────
def test_to_dict_includes_nested_profiles_when_present():
    u = User(user_id="u1")
    u.enable_player()
    u.enable_referee()
    as_map = u.to_dict()

    # structure checks
    assert isinstance(as_map, dict)
    assert as_map["user_id"] == "u1"
    assert isinstance(as_map["roles"], list) and len(as_map["roles"]) >= 1
    assert isinstance(as_map["player"], dict), "Player profile should be serialized as a dict"
    assert isinstance(as_map["referee"], dict), "Referee profile should be serialized as a dict"


# ─────────────────────────────────────────────────────────────
# Gentle behavior checks on profiles
# (just to show juniors what the defaults look like)
# ─────────────────────────────────────────────────────────────
def test_player_profile_defaults_are_safe():
    u = User()
    u.enable_player()
    p = u.player
    assert p is not None
    assert p.active_characters == []
    assert p.retired_characters == []
    assert p.quests_applied == 0
    assert p.quests_accepted == 0
    assert p.quest_summaries_written == []
    assert isinstance(p.played_with_counts, dict) and not p.played_with_counts


def test_referee_profile_defaults_are_safe():
    u = User()
    u.enable_referee()
    r = u.referee
    assert r is not None
    assert r.count_quests_dmed == 0
    assert r.quests_dmed == []
    assert r.dm_summaries_written == []
    assert r.current_count_sp == 0
    assert r.highest_count_sp == 0
    assert r.count_villains_run == 0
    assert isinstance(r.quest_hooks_pickedup, dict) and not r.quest_hooks_pickedup
    assert isinstance(r.games_run_by_region, dict) and not r.games_run_by_region
    assert isinstance(r.dms_collabed_with, dict) and not r.dms_collabed_with
    assert isinstance(r.dmed_for_counts, dict) and not r.dmed_for_counts
