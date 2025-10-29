from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from app.domain.models.LookupModel import LookupEntry
from app.infra.mongo import lookup_repo


class _FakeCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = list(docs)

    def sort(self, key: str, direction: int):
        reverse = direction < 0
        self._docs.sort(key=lambda item: item.get(key, ""), reverse=reverse)
        return self

    async def to_list(self, length: int) -> List[Dict[str, Any]]:
        if length <= 0:
            return []
        return self._docs[:length]


class _FakeCollection:
    def __init__(self):
        self._docs: Dict[Tuple[int, str], Dict[str, Any]] = {}
        self.last_find_one_and_update = None
        self.last_delete = None
        self.last_find_one = None

    async def find_one_and_update(self, filt, update, upsert=False, return_document=None):
        self.last_find_one_and_update = (filt, update, upsert, return_document)
        key = (filt["guild_id"], filt["name_normalized"])
        doc = update["$set"].copy()
        existing = self._docs.get(key)
        if existing is None:
            self._docs[key] = doc
        else:
            existing.update(doc)
            doc = existing
        return doc

    async def find_one(self, filt):
        self.last_find_one = filt
        key = (filt["guild_id"], filt["name_normalized"])
        return self._docs.get(key)

    def find(self, filt, projection):  # projection unused in fake
        guild_id = filt.get("guild_id")
        docs = [doc for (gid, _), doc in self._docs.items() if gid == guild_id]
        return _FakeCursor(docs)

    async def delete_one(self, filt):
        self.last_delete = filt
        key = (filt["guild_id"], filt["name_normalized"])
        existed = key in self._docs
        self._docs.pop(key, None)

        class _Result:
            deleted_count = 1 if existed else 0

        return _Result()


@pytest.mark.asyncio
async def test_upsert_scopes_by_guild(monkeypatch):
    repo = lookup_repo.LookupRepoMongo()
    fake = _FakeCollection()
    monkeypatch.setattr(lookup_repo, "COLL", lambda guild_id: fake)

    entry = LookupEntry(
        guild_id=321,
        name="Staff Guide",
        url="https://example.com",
        created_by=99,
    )
    saved = await repo.upsert(entry)

    filt, update, upsert, _ = fake.last_find_one_and_update
    assert filt == {"guild_id": 321, "name_normalized": "staff guide"}
    assert update["$set"]["guild_id"] == 321
    assert upsert is True
    assert saved.name == "Staff Guide"


@pytest.mark.asyncio
async def test_get_by_name_uses_normalized_key(monkeypatch):
    repo = lookup_repo.LookupRepoMongo()
    fake = _FakeCollection()
    fake._docs[(123, "faq")] = {
        "guild_id": 123,
        "name": "FAQ",
        "name_normalized": "faq",
        "url": "https://example.com/faq",
        "created_by": 1,
        "created_at": LookupEntry(
            guild_id=123,
            name="FAQ",
            url="https://example.com/faq",
            created_by=1,
        ).created_at,
    }
    monkeypatch.setattr(lookup_repo, "COLL", lambda guild_id: fake)

    result = await repo.get_by_name(123, "FAQ")

    assert fake.last_find_one == {"guild_id": 123, "name_normalized": "faq"}
    assert result is not None
    assert result.url == "https://example.com/faq"


@pytest.mark.asyncio
async def test_find_best_match_prefers_exact(monkeypatch):
    repo = lookup_repo.LookupRepoMongo()
    entries = [
        LookupEntry(guild_id=1, name="Guide", url="https://example.com/guide", created_by=1),
        LookupEntry(guild_id=1, name="Guidelines", url="https://example.com/guidelines", created_by=1),
    ]

    async def _list_all(_guild_id: int):
        return entries

    monkeypatch.setattr(repo, "list_all", _list_all)

    result = await repo.find_best_match(1, "guide")

    assert result is not None
    assert result.name == "Guide"


@pytest.mark.asyncio
async def test_delete_returns_bool(monkeypatch):
    repo = lookup_repo.LookupRepoMongo()
    fake = _FakeCollection()
    fake._docs[(1, "guide")] = {
        "guild_id": 1,
        "name": "Guide",
        "name_normalized": "guide",
        "url": "https://example.com/guide",
        "created_by": 1,
        "created_at": LookupEntry(
            guild_id=1,
            name="Guide",
            url="https://example.com/guide",
            created_by=1,
        ).created_at,
    }
    monkeypatch.setattr(lookup_repo, "COLL", lambda guild_id: fake)

    deleted = await repo.delete(1, "Guide")

    assert deleted is True
    assert fake.last_delete == {"guild_id": 1, "name_normalized": "guide"}
