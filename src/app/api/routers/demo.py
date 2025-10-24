from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Sequence

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

import os

from pymongo import MongoClient

from app.api.schemas import (
	LeaderboardEntry,
	LeaderboardMetric,
	LeaderboardResponse,
	UpcomingQuest,
	UpcomingQuestsResponse,
)

MONGO_URI = (os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or "").strip()
if not MONGO_URI:
	logging.getLogger(__name__).warning(
	"MONGODB_URI not set; demo endpoints will use the default localhost client."
	)

db_client = MongoClient(MONGO_URI) if MONGO_URI else MongoClient()

router = APIRouter(prefix="/demo", tags=["Demo"])


LEADERBOARD_FIELDS: dict[LeaderboardMetric, str] = {
	"messages": "messages_count_total",
	"reactions_given": "reactions_given",
	"reactions_received": "reactions_received",
	"voice": "voice_total_time_spent",
}


def _guild_db_names(target: str | None = None) -> Sequence[str]:
	names = []
	for name in db_client.list_database_names():
		if target and name != target:
			continue
		if name.isdigit():
			names.append(name)
	return names


def _coerce_entity_id(payload, prefix: str) -> str | None:
	if isinstance(payload, dict):
		value = payload.get("value")
		if isinstance(value, str) and value:
			return value
		number = payload.get("number")
		if number is not None:
			return f"{payload.get('prefix', prefix)}{number}"
	elif isinstance(payload, str) and payload:
		return payload
	elif isinstance(payload, int):
		return f"{prefix}{payload}"
	return None


async def _query_leaderboard(
	metric: LeaderboardMetric, guild_id: str | None
) -> LeaderboardResponse:
	field = LEADERBOARD_FIELDS[metric]

	def _fetch() -> LeaderboardResponse:
		rows: list[LeaderboardEntry] = []
		for db_name in _guild_db_names(guild_id):
			coll = db_client.get_database(db_name)["users"]
			cursor = (
				coll.find({field: {"$gt": 0}}, {"_id": 0, "discord_id": 1, field: 1})
				.sort(field, -1)
				.limit(10)
			)
			for doc in cursor:
				value = float(doc.get(field, 0))
				entry = LeaderboardEntry(
					guild_id=db_name,
					discord_id=(
						str(doc.get("discord_id")) if doc.get("discord_id") else None
					),
					metric=metric,
					value=value,
				)
				rows.append(entry)

		rows.sort(key=lambda e: e.value, reverse=True)
		return LeaderboardResponse(metric=metric, entries=rows[:10])

	return await asyncio.to_thread(_fetch)


async def _query_upcoming_quests(guild_id: str | None) -> UpcomingQuestsResponse:
	def _fetch() -> UpcomingQuestsResponse:
		quests: list[UpcomingQuest] = []
		now = datetime.now(timezone.utc)
		for db_name in _guild_db_names(guild_id):
			coll = db_client.get_database(db_name)["quests"]
			cursor = (
				coll.find({"starting_at": {"$gte": now}})
				.sort("starting_at", 1)
				.limit(10)
			)
			for doc in cursor:
				quest_label = _coerce_entity_id(doc.get("quest_id"), "QUES")
				if not quest_label:
					quest_label = (
						_coerce_entity_id(doc.get("_id"), "QUES") or "UNKNOWN"
					)

				referee_label = _coerce_entity_id(doc.get("referee_id"), "USER")
				quests.append(
					UpcomingQuest(
						guild_id=db_name,
						quest_id=quest_label,
						title=doc.get("title"),
						starting_at=doc.get("starting_at"),
						status=doc.get("status"),
						referee_id=referee_label,
					)
				)

		quests.sort(
			key=lambda q: q.starting_at or datetime.max.replace(tzinfo=timezone.utc)
		)
		return UpcomingQuestsResponse(quests=quests[:10])

	return await asyncio.to_thread(_fetch)


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def demo_leaderboard(
	metric: LeaderboardMetric = Query("messages"),
	guild_id: str | None = Query(None, description="Filter by guild id"),
) -> LeaderboardResponse:
	return await _query_leaderboard(metric, guild_id)


@router.get("/quests", response_model=UpcomingQuestsResponse)
async def demo_upcoming_quests(
	guild_id: str | None = Query(None, description="Filter by guild id"),
) -> UpcomingQuestsResponse:
	return await _query_upcoming_quests(guild_id)


@router.get("", response_class=HTMLResponse)
async def demo_page() -> str:
	return """<!DOCTYPE html>
<html lang=\"en\">
	<head>
	<meta charset=\"utf-8\" />
	<title>Nonagon Demo Dashboard</title>
	<style>
		body { font-family: system-ui, sans-serif; margin: 2rem; background: #0f172a; color: #e2e8f0; }
		h1 { color: #38bdf8; }
		section { margin-bottom: 2rem; }
		table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
		th, td { border: 1px solid #1e293b; padding: 0.5rem; text-align: left; }
		th { background: #1e293b; }
		.muted { color: #94a3b8; font-size: 0.9rem; }
		button { background: #38bdf8; border: none; padding: 0.5rem 1rem; color: #0f172a; border-radius: 4px; cursor: pointer; }
		button:hover { background: #0ea5e9; }
	</style>
	</head>
	<body>
	<h1>Nonagon Demo Dashboard</h1>
	<section>
		<h2>Leaderboards</h2>
		<div class=\"muted\">Top 10 users by chosen metric across demo guilds.</div>
		<div>
		<button onclick=\"loadLeaderboard('messages')\">Messages</button>
		<button onclick=\"loadLeaderboard('reactions_given')\">Reactions Given</button>
		<button onclick=\"loadLeaderboard('reactions_received')\">Reactions Received</button>
		<button onclick=\"loadLeaderboard('voice')\">Voice Hours</button>
		<select id=\"guildFilter\" onchange=\"onGuildChange()\">
			<option value=\"\">All Guilds</option>
		</select>
		</div>
		<table id=\"leaderboard\">
		<thead><tr><th>Rank</th><th>Guild</th><th>User</th><th>Value</th></tr></thead>
		<tbody></tbody>
		</table>
	</section>
	<section>
		<h2>Recent Summaries</h2>
		<table id=\"summaries\">
		<thead><tr><th>Guild</th><th>Kind</th><th>Quest</th><th>Character</th><th>Title</th><th>Created</th></tr></thead>
		<tbody></tbody>
		</table>
	</section>
	<section>
		<h2>Upcoming Quests</h2>
		<table id=\"quests\">
		<thead><tr><th>Guild</th><th>Quest</th><th>Title</th><th>Starts</th><th>Status</th></tr></thead>
		<tbody></tbody>
		</table>
	</section>
	<script>
		let currentGuild = '';
		async function loadGuilds() {
		const res = await fetch('/demo/guilds');
		const data = await res.json();
		const select = document.querySelector('#guildFilter');
		data.guilds.forEach(id => {
			const opt = document.createElement('option');
			opt.value = id;
			opt.innerText = id;
			select.appendChild(opt);
		});
		}
		function onGuildChange() {
		const sel = document.querySelector('#guildFilter');
		currentGuild = sel.value;
		loadLeaderboard('messages');
		loadQuests();
		loadSummaries();
		}
		async function loadLeaderboard(metric) {
		const res = await fetch(`/demo/leaderboard?metric=${metric}&guild_id=${currentGuild}`);
		const data = await res.json();
		const tbody = document.querySelector('#leaderboard tbody');
		tbody.innerHTML = '';
		data.entries.forEach((entry, idx) => {
			const row = document.createElement('tr');
			row.innerHTML = `<td>${idx + 1}</td><td>${entry.guild_id}</td><td>${entry.discord_id || 'N/A'}</td><td>${entry.value.toFixed(2)}</td>`;
			tbody.appendChild(row);
		});
		}

		async function loadQuests() {
		const res = await fetch(`/demo/quests?guild_id=${currentGuild}`);
		const data = await res.json();
		const tbody = document.querySelector('#quests tbody');
		tbody.innerHTML = '';
		data.quests.forEach((quest) => {
			const starts = quest.starting_at ? new Date(quest.starting_at).toLocaleString() : 'Unknown';
			const row = document.createElement('tr');
			row.innerHTML = `<td>${quest.guild_id}</td><td>${quest.quest_id}</td><td>${quest.title || 'Untitled'}</td><td>${starts}</td><td>${quest.status || 'ANNOUNCED'}</td>`;
			tbody.appendChild(row);
		});
		}
		async function loadSummaries() {
		const res = await fetch(`/demo/summaries?guild_id=${currentGuild}`);
		const data = await res.json();
		const tbody = document.querySelector('#summaries tbody');
		tbody.innerHTML = '';
		data.summaries.forEach((s) => {
			const created = s.created_on ? new Date(s.created_on).toLocaleString() : '';
			const row = document.createElement('tr');
			row.innerHTML = `<td>${s.guild_id}</td><td>${s.kind}</td><td>${s.quest_id}</td><td>${s.character_id}</td><td>${s.title || 'Untitled'}</td><td>${created}</td>`;
			tbody.appendChild(row);
		});
		}

		loadGuilds().then(() => { loadLeaderboard('messages'); loadQuests(); loadSummaries(); });
	</script>
	</body>
</html>"""


@router.get("/guilds")
async def demo_guilds() -> dict:
	names = [n for n in db_client.list_database_names() if str(n).isdigit()]
	return {"guilds": names}


@router.get("/summaries")
async def demo_recent_summaries(guild_id: str | None = None) -> dict:
	def _fetch() -> list[dict]:
		out: list[dict] = []
		for db_name in _guild_db_names(guild_id):
			coll = db_client.get_database(db_name)["summaries"]
			cursor = (
				coll.find({}, {"_id": 0, "kind": 1, "quest_id": 1, "character_id": 1, "title": 1, "created_on": 1})
				.sort("created_on", -1)
				.limit(10)
			)
			for doc in cursor:
				kind = doc.get("kind")
				qid = doc.get("quest_id", {})
				cid = doc.get("character_id", {})
				out.append(
					{
						"guild_id": db_name,
						"kind": kind if isinstance(kind, str) else str(kind),
			"quest_id": _coerce_entity_id(qid, "QUES") or str(qid),
			"character_id": _coerce_entity_id(cid, "CHAR") or str(cid),
						"title": doc.get("title"),
						"created_on": doc.get("created_on"),
					}
				)
		return out

	rows = await asyncio.to_thread(_fetch)
	return {"summaries": rows}
