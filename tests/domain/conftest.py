import pytest
from datetime import datetime

from app.domain.models.EntityIDModel import UserID, QuestID, CharacterID, SummaryID
from app.domain.models.UserModel import User, Player, Referee, Role

@pytest.fixture
def now():
	return datetime(2030, 1, 1, 12, 0, 0)

# ---- ID helpers ----
@pytest.fixture
def uid() -> UserID:
	return UserID(1)

@pytest.fixture
def qid() -> QuestID:
	return QuestID(1)

@pytest.fixture
def cid() -> CharacterID:
	return CharacterID(1)

@pytest.fixture
def sid() -> SummaryID:
	return SummaryID(1)

# ---- User helpers ----
@pytest.fixture
def base_user(uid: UserID) -> User:
	return User(user_id=uid)

@pytest.fixture
def player_user(uid: UserID) -> User:
	u = User(user_id=uid, roles=[Role.MEMBER, Role.PLAYER])
	u.player = Player()
	return u

@pytest.fixture
def referee_user(uid: UserID) -> User:
	u = User(user_id=uid, roles=[Role.MEMBER, Role.PLAYER, Role.REFEREE])
	u.player = Player()
	u.referee = Referee()
	return u
