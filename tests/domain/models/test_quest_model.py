# tests/test_quest_model.py
from datetime import datetime, timedelta
import pytest
from app.domain.models.QuestModel import Quest, QuestStatus
from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID


def make_quest(now: datetime) -> Quest:
	return Quest(
		quest_id=QuestID(1),
		guild_id=123,
		referee_id=UserID(99),
		channel_id="chan",
		message_id="msg",
		raw="# raw",
		title="Title",
		description="Desc",
		starting_at=None,
		duration=None,
		image_url=None,
	)


def test_quest_id_roundtrip():
	qid = QuestID(7)
	s = str(qid)
	assert qid == QuestID.parse(s)


def test_status_helpers_and_properties(now):
	q = make_quest(now)
	assert q.status is QuestStatus.ANNOUNCED
	assert q.is_signup_open is True

	q.set_draft()
	assert q.status is QuestStatus.DRAFT
	assert q.is_signup_open is False

	q.close_signups()
	assert q.status is QuestStatus.SIGNUP_CLOSED
	assert q.is_signup_open is False

	q.set_announced()
	assert q.status is QuestStatus.ANNOUNCED

	q.set_cancelled()
	assert q.status is QuestStatus.CANCELLED

	q.set_completed()
	assert q.status is QuestStatus.COMPLETED
	assert q.is_summary_needed is True  # none linked yet

	assert q.last_nudged_at is None


def test_add_and_select_signup():
	q = make_quest(datetime.now())
	uid = UserID(1)
	cid = CharacterID(1)

	q.add_signup(uid, cid)
	assert len(q.signups) == 1
	assert q.signups[0].user_id == uid

	# selecting non-existent should raise
	with pytest.raises(ValueError):
		q.select_signup(UserID(2))

	# selecting existing works
	q.select_signup(uid)
	assert q.signups[0].status.name == "SELECTED"


def test_remove_signup_removes_player():
	q = make_quest(datetime.now())
	uid = UserID(1)
	q.add_signup(uid, CharacterID(1))
	q.remove_signup(uid)
	assert len(q.signups) == 0


def test_validate_quest_duration_and_image_rules(now):
	q = make_quest(now)

	# Duration minimum with start provided (>=60 minutes when start present)
	q.starting_at = now + timedelta(days=1)
	q.duration = timedelta(minutes=30)
	with pytest.raises(ValueError):
		q.validate_quest()

	# Too short regardless (explicit 15-minute guard)
	q.duration = timedelta(minutes=10)
	with pytest.raises(ValueError):
		q.validate_quest()

	# Bad image URL
	q.duration = timedelta(minutes=90)
	q.image_url = "ftp://bad.example"
	with pytest.raises(ValueError):
		q.validate_quest()
