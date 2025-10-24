from __future__ import annotations

from typing import Any, Dict, Iterable, List

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routers import demo as demo_router


def test_healthz_ok():
	client = TestClient(app)
	resp = client.get("/healthz")
	assert resp.status_code == 200
	assert resp.json() == {"ok": True}


class _FakeCursor(list):
	def sort(self, *args, **kwargs):
		return self
	def limit(self, *args, **kwargs):
		return self


class _FakeCollection:
	def __init__(self, docs: List[Dict[str, Any]]):
		self._docs = docs
	def find(self, *args, **kwargs):
		return _FakeCursor(self._docs.copy())


class _FakeDB:
	def __init__(
		self,
		users: List[Dict[str, Any]] | None = None,
		quests: List[Dict[str, Any]] | None = None,
		summaries: List[Dict[str, Any]] | None = None,
	):
		self._users = users or []
		self._quests = quests or []
		self._summaries = summaries or []
	def __getitem__(self, name: str):
		if name == "users":
			return _FakeCollection(self._users)
		if name == "quests":
			return _FakeCollection(self._quests)
		if name == "summaries":
			return _FakeCollection(self._summaries)
		raise KeyError(name)


class _FakeClient:
	def __init__(self, dbs: Dict[str, _FakeDB]):
		self._dbs = dbs
	def list_database_names(self) -> Iterable[str]:
		return list(self._dbs.keys())
	def get_database(self, name: str) -> _FakeDB:
		return self._dbs[name]


def test_demo_html():
	client = TestClient(app)
	resp = client.get("/demo")
	assert resp.status_code == 200
	assert "text/html" in resp.headers.get("content-type", "")


def test_demo_leaderboard_and_quests(monkeypatch):
	fake = _FakeClient(
		{
			"123": _FakeDB(
				users=[{"discord_id": "111", "messages_count_total": 5}],
				quests=[
					{
						"quest_id": {"prefix": "QUES", "value": "QUESA1B2C3"},
						"referee_id": {"prefix": "USER", "value": "USERD4E5F6"},
						"title": "Seeded",
						"starting_at": None,
						"status": "ANNOUNCED",
					}
				],
				# add one summary doc
				summaries=[
					{
						"kind": "PLAYER",
						"quest_id": {"prefix": "QUES", "value": "QUESA1B2C3"},
						"character_id": {"prefix": "CHAR", "value": "CHARA1B2C3"},
						"title": "Recap",
						"created_on": None,
					}
				],
			)
		}
	)

	monkeypatch.setattr(demo_router, "db_client", fake)
	client = TestClient(app)

	lb = client.get("/demo/leaderboard?metric=messages")
	assert lb.status_code == 200
	body = lb.json()
	assert body["metric"] == "messages"
	assert body["entries"] and body["entries"][0]["value"] == 5.0

	quests = client.get("/demo/quests")
	assert quests.status_code == 200
	qbody = quests.json()
	assert qbody["quests"] and qbody["quests"][0]["quest_id"].startswith("QUES")

	gids = client.get("/demo/guilds")
	assert gids.status_code == 200
	assert "123" in gids.json().get("guilds", [])

	sums = client.get("/demo/summaries")
	assert sums.status_code == 200
	sbody = sums.json()
	assert sbody["summaries"] and sbody["summaries"][0]["kind"] == "PLAYER"
