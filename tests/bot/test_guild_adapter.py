from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from app.domain.models.CharacterModel import Character  # noqa: E402
from app.domain.models.EntityIDModel import QuestID, UserID  # noqa: E402
from app.domain.models.QuestModel import Quest  # noqa: E402
from app.domain.models.UserModel import User  # noqa: E402
from app.infra.mongo.guild_adapter import (  # noqa: E402
    upsert_character_sync,
    upsert_quest_sync,
    upsert_user_sync,
)
from app.infra.serialization import from_bson, to_bson  # noqa: E402


class _FakeCollection:
    def __init__(self):
        self.last = None
        self.indexes = []

    def create_index(self, keys, **kwargs):
        self.indexes.append((tuple(keys), kwargs))
        return kwargs.get("name")

    def update_one(
        self, filt: Dict[str, Any], doc: Dict[str, Any], upsert: bool = False
    ):
        self.last = (filt, doc, upsert)


class _FakeDB:
    def __init__(self):
        self._users = _FakeCollection()
        self._quests = _FakeCollection()
        self._characters = _FakeCollection()

    def __getitem__(self, name: str):
        if name == "users":
            return self._users
        if name == "quests":
            return self._quests
        if name == "characters":
            return self._characters
        raise KeyError


class _FakeClient:
    def __init__(self):
        self._db = _FakeDB()

    def get_database(self, name: str):
        assert name.isdigit()
        return self._db


def test_upsert_user_sync_builds_filter():
    client = _FakeClient()
    user = User(user_id=UserID(42))
    upsert_user_sync(client, guild_id=123, user=user)
    filt, doc, upsert = client._db._users.last
    assert filt == {"guild_id": 123, "user_id.value": str(user.user_id)}
    assert upsert is True
    payload = doc["$set"]
    assert payload["user_id"]["value"] == str(user.user_id)
    assert payload["guild_id"] == 123
    index_keys = [keys for keys, _ in client._db._users.indexes]
    assert (("guild_id", 1), ("user_id.value", 1)) in index_keys
    assert (("guild_id", 1), ("discord_id", 1)) in index_keys


def test_upsert_quest_sync_builds_filter():
    client = _FakeClient()
    q = Quest(
        quest_id=QuestID(7),
        guild_id=123,
        referee_id=UserID(1),
        channel_id="0",
        message_id="0",
        raw="x",
    )
    upsert_quest_sync(client, guild_id=123, quest=q)
    filt, doc, upsert = client._db._quests.last
    assert filt == {"guild_id": 123, "quest_id.value": str(q.quest_id)}
    assert upsert is True
    payload = doc["$set"]
    assert payload["quest_id"]["value"] == str(q.quest_id)
    assert payload["guild_id"] == 123
    quest_indexes = [keys for keys, _ in client._db._quests.indexes]
    assert (("guild_id", 1), ("quest_id.value", 1)) in quest_indexes
    assert (("guild_id", 1), ("channel_id", 1), ("message_id", 1)) in quest_indexes


def test_upsert_character_sync_builds_filter():
    client = _FakeClient()
    c = Character(
        character_id="CHAR0003",
        owner_id=UserID(1),
        name="N",
        ddb_link="d",
        character_thread_link="t",
        token_link="k",
        art_link="a",
    )
    upsert_character_sync(client, guild_id=123, character=c)
    filt, doc, upsert = client._db._characters.last
    assert filt == {"guild_id": 123, "character_id": c.character_id}
    assert upsert is True
    payload = doc["$set"]
    assert payload["guild_id"] == 123
    char_indexes = [keys for keys, _ in client._db._characters.indexes]
    assert (("guild_id", 1), ("character_id", 1)) in char_indexes
    assert (("guild_id", 1), ("owner_id.value", 1)) in char_indexes


def test_user_serialization_roundtrip_guild_id():
    user = User(user_id=UserID(1), guild_id=555)
    doc = to_bson(user)
    assert doc["guild_id"] == 555
    restored = from_bson(User, doc)
    assert restored.guild_id == 555
