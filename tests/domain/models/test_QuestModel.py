# tests/domain/models/test_quest.py
from datetime import datetime, timedelta

from app.domain.models.quest.QuestModel import (
    Quest,
    QuestStatus,
    SignupStatus,
)


# ─────────────────────────────────────────────────────────────
# 1) Construction & safe defaults
# ─────────────────────────────────────────────────────────────
def test_quest_defaults_are_safe():
    q = Quest(quest_id="q1", name="Grave of the Dawn", dm_id="u_dm")
    assert q.status is QuestStatus.DRAFT
    assert q.signups == []
    assert q.roster == []
    assert q.waitlist == []
    assert q.summary_ids == []
    assert q.attendees == []
    assert q.sessions_cancelled_count == 0
    assert q.max_players == 5 and q.min_players == 3


def test_mutable_fields_not_shared_between_instances():
    q1 = Quest(quest_id="q1", name="A", dm_id="u")
    q2 = Quest(quest_id="q2", name="B", dm_id="u")
    q1.tags.append("hardcore")
    q1.summary_ids.append("s1")
    q1.signups.append(q1.signups.__class__.__args__[0] if hasattr(q1.signups, "__args__") else None)  # sanity; won't change q2
    assert q2.tags == []
    assert q2.summary_ids == []
    assert q2.signups == []


# ─────────────────────────────────────────────────────────────
# 2) Opening signups & simple flags
# ─────────────────────────────────────────────────────────────
def test_open_signups_sets_status_and_timestamps():
    q = Quest(quest_id="q1", name="Night Market", dm_id="u_dm")
    q.open_signups()
    assert q.status is QuestStatus.SIGNUP_OPEN
    assert isinstance(q.status_updated_at, datetime)
    assert q.updated_at == q.status_updated_at
    assert q.is_signup_open() is True


# ─────────────────────────────────────────────────────────────
# 3) Adding signups
# ─────────────────────────────────────────────────────────────
def test_add_signup_appends_and_sets_defaults():
    q = Quest(quest_id="q1", name="Bridge of Crows", dm_id="u_dm")
    q.add_signup(user_id="u1", character_id="c1", note="can play 2h late")
    assert len(q.signups) == 1
    s = q.signups[0]
    assert (s.user_id, s.character_id) == ("u1", "c1")
    assert s.status is SignupStatus.APPLIED
    assert isinstance(s.applied_at, datetime)
    assert isinstance(s.updated_at, datetime)
    assert s.note == "can play 2h late"


# ─────────────────────────────────────────────────────────────
# 4) Roster selection updates roster, waitlist, and signup statuses
# ─────────────────────────────────────────────────────────────
def test_select_roster_updates_everything_consistently():
    q = Quest(quest_id="q1", name="Gilded Labyrinth", dm_id="u_dm", max_players=2)

    # three players applied
    q.add_signup("u1", "c1")
    q.add_signup("u2", "c2")
    q.add_signup("u3", "c3")

    # choose 2, waitlist 1
    q.select_roster(selected=[("u1", "c1"), ("u2", "c2")], waitlisted=[("u3", "c3")])

    # lifecycle
    assert q.status is QuestStatus.ROSTER_SELECTED
    assert len(q.roster) == 2
    assert len(q.waitlist) == 1

    # corresponding signup statuses updated
    by_key = {(s.user_id, s.character_id): s for s in q.signups}
    assert by_key[("u1", "c1")].status is SignupStatus.SELECTED
    assert by_key[("u2", "c2")].status is SignupStatus.SELECTED
    assert by_key[("u3", "c3")].status is SignupStatus.WAITLISTED

    # timestamps touched
    assert q.updated_at == q.status_updated_at
    assert all(isinstance(r.selected_at, datetime) for r in q.roster)


def test_select_roster_handles_none_waitlist_and_leaves_others_applied():
    q = Quest(quest_id="q1", name="Temple of Rain", dm_id="u_dm")
    q.add_signup("u1", "c1")
    q.add_signup("u2", "c2")
    q.add_signup("u3", "c3")

    q.select_roster(selected=[("u1", "c1")])  # waitlisted=None

    by_key = {(s.user_id, s.character_id): s for s in q.signups}
    assert by_key[("u1", "c1")].status is SignupStatus.SELECTED
    # others remain APPLIED (no implicit decline)
    assert by_key[("u2", "c2")].status is SignupStatus.APPLIED
    assert by_key[("u3", "c3")].status is SignupStatus.APPLIED


# ─────────────────────────────────────────────────────────────
# 5) Capacity helpers
# ─────────────────────────────────────────────────────────────
def test_capacity_remaining_never_negative():
    q = Quest(quest_id="q1", name="The Stringless Harp", dm_id="u_dm", max_players=1)
    # simulate selection
    q.select_roster(selected=[("u1", "c1")])
    assert q.capacity_remaining() == 0  # not -1


# ─────────────────────────────────────────────────────────────
# 6) Running → Completed → Cancelled
# ─────────────────────────────────────────────────────────────
def test_mark_running_sets_status_and_started_at():
    q = Quest(quest_id="q1", name="Saffron Road", dm_id="u_dm")
    q.mark_running()
    assert q.status is QuestStatus.RUNNING
    assert isinstance(q.started_at, datetime)
    assert q.updated_at == q.status_updated_at == q.started_at


def test_mark_completed_sets_summary_needed_and_ended_at():
    q = Quest(quest_id="q1", name="Ivory Gate", dm_id="u_dm")
    q.mark_completed()
    assert q.status is QuestStatus.COMPLETED
    assert q.summary_needed is True
    assert isinstance(q.ended_at, datetime)
    assert q.updated_at == q.status_updated_at == q.ended_at


def test_cancel_increments_counter_and_sets_reason():
    q = Quest(quest_id="q1", name="Starfall Ferry", dm_id="u_dm")
    q.cancel("DM ill")
    assert q.status is QuestStatus.CANCELLED
    assert q.cancellation_reason == "DM ill"
    assert isinstance(q.cancelled_at, datetime)
    assert q.sessions_cancelled_count == 1
    assert q.updated_at == q.status_updated_at == q.cancelled_at


# ─────────────────────────────────────────────────────────────
# 7) Quick linkage sanity (Discord fields optional)
# ─────────────────────────────────────────────────────────────
def test_discord_linkage_fields_are_optional():
    q = Quest(quest_id="q1", name="Silent Orchard", dm_id="u_dm")
    assert q.guild_id is None and q.channel_id is None
    assert q.signup_message_id is None and q.thread_id is None
