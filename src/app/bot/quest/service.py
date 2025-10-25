from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Type

import aiohttp
import discord
from discord.abc import Messageable
from discord.ext import commands

from app.bot.config import (
	BOT_FLUSH_VIA_ADAPTER,
	FORGE_CHANNEL_IDS,
	QUEST_API_BASE_URL,
	QUEST_BOARD_CHANNEL_ID,
)
from app.bot.quest.models import (
	ForgeDraft,
	ForgePreviewState,
)
from app.bot.utils.log_stream import send_demo_log
from app.bot.services import guild_settings_store
from app.bot.utils.quest_embeds import (
	QuestEmbedData,
	QuestEmbedRoster,
	build_quest_embed,
)
from app.domain.models.EntityIDModel import CharacterID, EntityID, QuestID, UserID
from app.domain.models.QuestModel import PlayerSignUp, PlayerStatus, Quest, QuestStatus
from app.domain.models.UserModel import User
from app.infra.mongo.guild_adapter import upsert_quest_sync
from app.infra.mongo.users_repo import UsersRepoMongo
from app.infra.serialization import to_bson


class QuestService:
	"""Encapsulates quest persistence and orchestration logic for the bot."""

	def __init__(self, bot: commands.Bot) -> None:
		self.bot = bot
		self._forge_previews: dict[tuple[int, int], ForgePreviewState] = {}
		self._demo_log = send_demo_log
		self._users_repo = UsersRepoMongo()

	# ------------------------------------------------------------------
	# Forge helpers

	def is_forge_channel(self, channel: Optional[Messageable]) -> bool:
		if channel is None:
			return False

		channel_id = getattr(channel, "id", None)
		if channel_id is None:
			return False

		guild = getattr(channel, "guild", None)
		if isinstance(guild, discord.Guild):
			settings = guild_settings_store.fetch_settings(guild.id) or {}
			stored_id = settings.get("quest_forge_channel_id")
			try:
				if stored_id is not None and int(stored_id) == int(channel_id):
					return True
			except (TypeError, ValueError):
				pass

		if FORGE_CHANNEL_IDS:
			return int(channel_id) in FORGE_CHANNEL_IDS

		return False

	def forge_preview_state(self, guild_id: int, message_id: int) -> ForgePreviewState:
		key = (guild_id, message_id)
		state = self._forge_previews.get(key)
		if state is None:
			state = ForgePreviewState()
			self._forge_previews[key] = state
		return state

	async def cleanup_forge_preview(self, guild: discord.Guild, message_id: int) -> None:
		state = self._forge_previews.pop((guild.id, message_id), None)
		if state is None:
			return

		if state.thread_id:
			thread = guild.get_thread(state.thread_id)
			if thread is None:
				try:
					thread = await guild.fetch_channel(state.thread_id)
				except Exception:
					thread = None
			if isinstance(thread, discord.Thread):
				try:
					await thread.delete()
				except Exception:
					pass

	async def resolve_board_channel(
		self, guild: discord.Guild, fallback: discord.TextChannel
	) -> Messageable:
		if QUEST_BOARD_CHANNEL_ID:
			channel = guild.get_channel(QUEST_BOARD_CHANNEL_ID)
			if channel is None:
				try:
					channel = await guild.fetch_channel(QUEST_BOARD_CHANNEL_ID)
				except Exception:
					channel = None
			if channel is not None:
				return channel
		return fallback

	# ------------------------------------------------------------------
	# Quest embeds

	def lookup_user_display(self, guild_id: int, user_id: UserID) -> str:
		guild_entry = self.bot.guild_data.get(guild_id)
		if guild_entry:
			for cached in guild_entry.get("users", {}).values():
				try:
					if cached.user_id == user_id:
						if cached.discord_id:
							return f"<@{cached.discord_id}>"
						return str(cached.user_id)
				except AttributeError:
					continue
		return str(user_id)

	def format_signup_label(self, guild_id: int, signup: PlayerSignUp) -> str:
		user_display = self.lookup_user_display(guild_id, signup.user_id)
		return f"{user_display} — {str(signup.character_id)}"

	def quest_to_embed_data(
		self,
		quest: Quest,
		guild: Optional[discord.Guild],
		*,
		referee_display: Optional[str] = None,
		approved_by_display: Optional[str] = None,
		last_updated_at: Optional[datetime] = None,
	) -> QuestEmbedData:
		roster_selected: list[str] = []
		roster_pending: list[str] = []
		for signup in quest.signups:
			label = (
				f"{self.lookup_user_display(quest.guild_id, signup.user_id)} — {str(signup.character_id)}"
			)
			if signup.status is PlayerStatus.SELECTED:
				roster_selected.append(label)
			else:
				roster_pending.append(label)

		roster = QuestEmbedRoster(selected=roster_selected, pending=roster_pending)

		referee_label = referee_display
		if referee_label is None:
			referee_label = self.lookup_user_display(quest.guild_id, quest.referee_id)

		data = QuestEmbedData(
			quest_id=str(quest.quest_id),
			title=quest.title,
			description=quest.description,
			status=quest.status,
			starting_at=quest.starting_at,
			duration=quest.duration,
			referee_display=referee_label,
			roster=roster,
			image_url=quest.image_url,
			last_updated_at=last_updated_at or datetime.now(timezone.utc),
			approved_by_display=approved_by_display,
		)
		return data

	def build_quest_embed(
		self,
		quest: Quest,
		guild: Optional[discord.Guild],
		*,
		referee_display: Optional[str] = None,
		approved_by_display: Optional[str] = None,
		last_updated_at: Optional[datetime] = None,
	) -> discord.Embed:
		data = self.quest_to_embed_data(
			quest,
			guild,
			referee_display=referee_display,
			approved_by_display=approved_by_display,
			last_updated_at=last_updated_at,
		)
		return build_quest_embed(data)

	def build_nudge_embed(
		self,
		quest: Quest,
		member: discord.Member,
		jump_url: str,
		*,
		bumped_at: datetime,
	) -> discord.Embed:
		quest_title = quest.title or str(quest.quest_id)
		embed = discord.Embed(
			title=f"Quest Nudge: {quest_title}",
			description=(
				f"{member.mention} bumped this quest.\n"
				f"[View announcement]({jump_url})"
			),
			color=discord.Color.gold(),
			timestamp=bumped_at,
		)

		if quest.starting_at:
			start_ts = quest.starting_at
			if start_ts.tzinfo is None or start_ts.tzinfo.utcoffset(start_ts) is None:
				start_ts = start_ts.replace(tzinfo=timezone.utc)
			embed.add_field(
				name="Start Time",
				value=f"<t:{int(start_ts.timestamp())}:F>",
				inline=False,
			)

		embed.set_footer(text=f"Quest ID: {quest.quest_id}")
		return embed

	def build_draft_embed(
		self,
		draft: ForgeDraft,
		*,
		quest_id: str,
		referee_display: str,
		status: QuestStatus = QuestStatus.DRAFT,
	) -> discord.Embed:
		roster = QuestEmbedRoster()
		data = QuestEmbedData(
			quest_id=quest_id,
			title=draft.title,
			description=draft.description,
			status=status,
			starting_at=draft.starting_at,
			duration=draft.duration,
			referee_display=referee_display,
			roster=roster,
			image_url=draft.image_url,
			last_updated_at=datetime.now(timezone.utc),
			approved_by_display=referee_display,
		)
		return build_quest_embed(data)

	# ------------------------------------------------------------------
	# Persistence helpers

	async def ensure_guild_cache(self, guild: discord.Guild) -> None:
		if guild.id not in self.bot.guild_data:
			await self.bot.load_or_create_guild_cache(guild)

	async def get_cached_user(self, member: discord.Member) -> User:
		await self.ensure_guild_cache(member.guild)
		guild_entry = self.bot.guild_data[member.guild.id]

		user = guild_entry["users"].get(member.id)
		if user is not None:
			return user

		listener: Optional[commands.Cog] = self.bot.get_cog("ListnerCog")
		if listener is None:
			raise RuntimeError("Listener cog not loaded; cannot resolve users.")

		ensure_method = getattr(listener, "_ensure_cached_user", None)
		if ensure_method is None:
			raise RuntimeError("Listener cog missing _ensure_cached_user helper.")

		user = await ensure_method(member)  # type: ignore[misc]
		return user

	async def resolve_member_for_user_id(
		self, guild: discord.Guild, user_id: UserID
	) -> Optional[discord.Member]:
		await self.ensure_guild_cache(guild)
		guild_entry = self.bot.guild_data.get(guild.id)

		def _coerce_discord_id(raw: object) -> int | None:
			if isinstance(raw, int):
				return raw
			if isinstance(raw, str):
				digits = raw.strip()
				if digits.isdigit():
					return int(digits)
			return None

		candidate_ids: set[int] = set()

		if guild_entry:
			users = guild_entry.get("users", {})
			for cached_discord_id, cached_user in users.items():
				try:
					if cached_user.user_id != user_id:
						continue
					parsed = _coerce_discord_id(cached_discord_id)
					if parsed is not None:
						candidate_ids.add(parsed)
					cached_value = getattr(cached_user, "discord_id", None)
					parsed = _coerce_discord_id(cached_value)
					if parsed is not None:
						candidate_ids.add(parsed)
				except AttributeError:
					continue

		try:
			repo_user = await self._users_repo.get(guild.id, str(user_id))
		except Exception:
			repo_user = None
		if repo_user is not None:
			parsed = _coerce_discord_id(getattr(repo_user, "discord_id", None))
			if parsed is not None:
				candidate_ids.add(parsed)

		for discord_id in candidate_ids:
			member = guild.get_member(discord_id)
			if member is not None:
				return member
			try:
				member = await guild.fetch_member(discord_id)
			except Exception:
				continue
			if member is not None:
				return member

		return None

	def parse_entity_id(
		self, cls: Type[EntityID], payload: Any, *, fallback: Any = None
	) -> EntityID:
		if isinstance(payload, cls):
			return payload
		if isinstance(payload, dict):
			value = payload.get("value")
			if isinstance(value, str) and value:
				return cls.parse(value)
			number = payload.get("number")
			if number is not None:
				prefix = payload.get("prefix", cls.prefix)
				return cls.parse(f"{prefix}{number}")
		if isinstance(payload, str) and payload:
			return cls.parse(payload)
		if isinstance(payload, int):
			return cls.parse(f"{cls.prefix}{payload}")
		if fallback is not None:
			return self.parse_entity_id(cls, fallback)
		raise ValueError(f"Unable to parse {cls.__name__} from payload={payload!r}")

	def next_quest_id(self, guild_id: int) -> QuestID:
		guild_entry = self.bot.guild_data[guild_id]
		db = guild_entry["db"]
		coll = db["quests"]
		while True:
			candidate = QuestID.generate()
			exists = coll.count_documents(
				{"guild_id": guild_id, "quest_id.value": str(candidate)}, limit=1
			)
			if not exists:
				return candidate

	def quest_to_doc(self, quest: Quest) -> dict:
		doc = to_bson(quest)
		doc["guild_id"] = quest.guild_id
		return doc

	def persist_quest(self, guild_id: int, quest: Quest) -> None:
		if BOT_FLUSH_VIA_ADAPTER:
			from app.bot.database import db_client

			upsert_quest_sync(db_client, guild_id, quest)
			return
		guild_entry = self.bot.guild_data[guild_id]
		db = guild_entry["db"]
		quest.guild_id = guild_id
		payload = self.quest_to_doc(quest)
		db["quests"].update_one(
			{"guild_id": guild_id, "quest_id.value": str(quest.quest_id)},
			{"$set": payload},
			upsert=True,
		)

	async def persist_quest_via_api(self, guild: discord.Guild, quest: Quest) -> bool:
		if not QUEST_API_BASE_URL:
			return False

		base_url = QUEST_API_BASE_URL.rstrip("/")
		url = f"{base_url}/v1/guilds/{guild.id}/quests"
		payload: dict[str, object] = {
			"quest_id": str(quest.quest_id),
			"referee_id": str(quest.referee_id),
			"raw": quest.raw,
			"title": quest.title,
			"description": quest.description,
			"image_url": quest.image_url,
			"linked_quests": [str(qid) for qid in quest.linked_quests],
			"linked_summaries": [str(sid) for sid in quest.linked_summaries],
		}

		if quest.starting_at is not None:
			payload["starting_at"] = quest.starting_at.isoformat()

		if quest.duration is not None:
			payload["duration_hours"] = int(quest.duration.total_seconds() // 3600)

		params = {
			"channel_id": quest.channel_id,
			"message_id": quest.message_id,
		}

		timeout = aiohttp.ClientTimeout(total=10)
		try:
			async with aiohttp.ClientSession(timeout=timeout) as session:
				async with session.post(url, json=payload, params=params) as resp:
					if resp.status != 201:
						text = await resp.text()
						raise RuntimeError(
							f"Quest API persistence failed with {resp.status}: {text}"
						)
			return True
		except Exception as exc:
			logging.warning(
				"Falling back to direct quest persistence for %s in guild %s: %s",
				quest.quest_id,
				guild.id,
				exc,
			)
			return False

	async def add_signup_via_api(
		self,
		guild: discord.Guild,
		quest: Quest,
		user: User,
		character_id: CharacterID,
	) -> bool:
		if not QUEST_API_BASE_URL:
			return False

		base_url = QUEST_API_BASE_URL.rstrip("/")
		url = f"{base_url}/v1/guilds/{guild.id}/quests/{quest.quest_id}/signups"
		payload = {
			"user_id": str(user.user_id),
			"character_id": str(character_id),
		}

		timeout = aiohttp.ClientTimeout(total=10)
		try:
			async with aiohttp.ClientSession(timeout=timeout) as session:
				async with session.post(url, json=payload) as resp:
					if resp.status in (200, 201):
						return True

					raw = await resp.text()
					detail = self.extract_api_detail(raw)

					if resp.status in (400, 404):
						message = self.normalize_signup_error(
							detail or "Unable to submit signup request."
						)
						raise ValueError(message)

					logging.warning(
						"Signup API returned %s for quest %s in guild %s: %s",
						resp.status,
						quest.quest_id,
						guild.id,
						detail or raw,
					)
					return False
		except ValueError:
			raise
		except Exception as exc:
			logging.warning(
				"Signup API request failed for quest %s in guild %s: %s",
				quest.quest_id,
				guild.id,
				exc,
			)
			return False

	async def select_signup_via_api(
		self,
		guild: discord.Guild,
		quest: Quest,
		user_id: UserID,
	) -> bool:
		if not QUEST_API_BASE_URL:
			return False

		base_url = QUEST_API_BASE_URL.rstrip("/")
		url = f"{base_url}/v1/guilds/{guild.id}/quests/{quest.quest_id}/signups/{user_id}:select"

		timeout = aiohttp.ClientTimeout(total=10)
		try:
			async with aiohttp.ClientSession(timeout=timeout) as session:
				async with session.post(url) as resp:
					if resp.status in (200, 201):
						return True

					raw = await resp.text()
					detail = self.extract_api_detail(raw)

					if resp.status in (400, 404):
						raise ValueError(detail or "Unable to accept signup request.")

					logging.warning(
						"Signup select API returned %s for quest %s in guild %s: %s",
						resp.status,
						quest.quest_id,
						guild.id,
						detail or raw,
					)
					return False
		except ValueError:
			raise
		except Exception as exc:
			logging.warning(
				"Signup select API request failed for quest %s in guild %s: %s",
				quest.quest_id,
				guild.id,
				exc,
			)
			return False

	async def remove_signup_via_api(
		self,
		guild: discord.Guild,
		quest: Quest,
		user_id: UserID,
	) -> bool:
		if not QUEST_API_BASE_URL:
			return False

		base_url = QUEST_API_BASE_URL.rstrip("/")
		url = f"{base_url}/v1/guilds/{guild.id}/quests/{quest.quest_id}/signups/{user_id}"

		timeout = aiohttp.ClientTimeout(total=10)
		try:
			async with aiohttp.ClientSession(timeout=timeout) as session:
				async with session.delete(url) as resp:
					if resp.status in (200, 204):
						return True

					raw = await resp.text()
					detail = self.extract_api_detail(raw)

					if resp.status in (400, 404):
						raise ValueError(detail or "Unable to remove signup.")

					logging.warning(
						"Signup removal API returned %s for quest %s in guild %s: %s",
						resp.status,
						quest.quest_id,
						guild.id,
						detail or raw,
					)
					return False
		except ValueError:
			raise
		except Exception as exc:
			logging.warning(
				"Signup removal API request failed for quest %s in guild %s: %s",
				quest.quest_id,
				guild.id,
				exc,
			)
			return False

	async def nudge_via_api(
		self,
		guild: discord.Guild,
		quest: Quest,
		referee: User,
	) -> tuple[bool, Optional[datetime]]:
		if not QUEST_API_BASE_URL:
			return False, None

		base_url = QUEST_API_BASE_URL.rstrip("/")
		url = f"{base_url}/v1/guilds/{guild.id}/quests/{quest.quest_id}:nudge"
		payload = {"referee_id": str(referee.user_id)}

		timeout = aiohttp.ClientTimeout(total=10)
		try:
			async with aiohttp.ClientSession(timeout=timeout) as session:
				async with session.post(url, json=payload) as resp:
					if resp.status in (200, 201):
						api_timestamp: Optional[datetime] = None
						try:
							data = await resp.json()
						except Exception:
							data = None
						if isinstance(data, dict):
							raw_ts = data.get("last_nudged_at")
							if isinstance(raw_ts, str):
								iso_value = raw_ts.strip()
								if iso_value.endswith("Z"):
									iso_value = iso_value[:-1] + "+00:00"
								try:
									api_timestamp = datetime.fromisoformat(iso_value)
								except ValueError:
									api_timestamp = None
						return True, api_timestamp

					raw = await resp.text()
					detail = self.extract_api_detail(raw)

					if resp.status in (400, 404):
						raise ValueError(detail or "Unable to nudge quest.")

					logging.warning(
						"Nudge API returned %s for quest %s in guild %s: %s",
						resp.status,
						quest.quest_id,
						guild.id,
						detail or raw,
					)
					return False, None
		except ValueError:
			raise
		except Exception as exc:
			logging.warning(
				"Nudge API request failed for quest %s in guild %s: %s",
				quest.quest_id,
				guild.id,
				exc,
			)
			return False, None

	async def emit_nudge_log(
		self,
		guild: discord.Guild,
		member: discord.Member,
		quest_title: str,
	) -> None:
		message = f"{member.mention} nudged quest `{quest_title}`"
		try:
			await self._demo_log(self.bot, guild, message)
		except Exception as exc:
			logging.warning(
				"Failed to emit nudge log for quest %s in guild %s",
				quest_title,
				getattr(guild, "id", "unknown"),
				exc_info=exc,
			)

	async def close_signups_via_api(
		self,
		guild: discord.Guild,
		quest: Quest,
	) -> bool:
		if not QUEST_API_BASE_URL:
			return False

		base_url = QUEST_API_BASE_URL.rstrip("/")
		url = f"{base_url}/v1/guilds/{guild.id}/quests/{quest.quest_id}:closeSignups"

		timeout = aiohttp.ClientTimeout(total=10)
		try:
			async with aiohttp.ClientSession(timeout=timeout) as session:
				async with session.post(url) as resp:
					if resp.status in (200, 201):
						return True

					raw = await resp.text()
					detail = self.extract_api_detail(raw)

					if resp.status in (400, 404):
						raise ValueError(detail or "Unable to close signups.")

					logging.warning(
						"Close signups API returned %s for quest %s in guild %s: %s",
						resp.status,
						quest.quest_id,
						guild.id,
						detail or raw,
					)
					return False
		except ValueError:
			raise
		except Exception as exc:
			logging.warning(
				"Close signups API request failed for quest %s in guild %s: %s",
				quest.quest_id,
				guild.id,
				exc,
			)
			return False

	# ------------------------------------------------------------------
	# Quest data access

	def quest_from_doc(self, guild_id: int, doc: dict) -> Quest:
		quest_id_doc = doc.get("quest_id")
		ref_doc = doc.get("referee_id")
		stored_gid = doc.get("guild_id", guild_id)

		ref_payload = ref_doc if ref_doc else doc.get("referee")

		quest = Quest(
			quest_id=self.parse_entity_id(QuestID, quest_id_doc, fallback=doc.get("_id")),
			guild_id=int(stored_gid),
			referee_id=self.parse_entity_id(UserID, ref_payload),
			channel_id=doc["channel_id"],
			message_id=doc["message_id"],
			raw=doc.get("raw", ""),
			title=doc.get("title"),
			description=doc.get("description"),
			starting_at=doc.get("starting_at"),
			duration=(
				timedelta(seconds=float(doc["duration"]))
				if doc.get("duration") is not None
				else None
			),
			image_url=doc.get("image_url"),
		)

		status_value = doc.get("status")
		if status_value:
			quest.status = (
				status_value
				if isinstance(status_value, QuestStatus)
				else QuestStatus(status_value)
			)

		quest.started_at = doc.get("started_at")
		quest.ended_at = doc.get("ended_at")
		quest.last_nudged_at = doc.get("last_nudged_at")

		signups: list[PlayerSignUp] = []
		for entry in doc.get("signups", []):
			uid = entry.get("user_id")
			cid = entry.get("character_id")
			status = entry.get("status")
			if uid is None or cid is None:
				continue
			user_id = self.parse_entity_id(UserID, uid)
			char_id = self.parse_entity_id(CharacterID, cid)
			signups.append(
				PlayerSignUp(
					user_id=user_id,
					character_id=char_id,
					status=(
						status
						if isinstance(status, PlayerStatus)
						else PlayerStatus(status) if status else PlayerStatus.APPLIED
					),
				)
			)

		quest.signups = signups
		return quest

	def fetch_quest(self, guild_id: int, quest_id: QuestID) -> Optional[Quest]:
		guild_entry = self.bot.guild_data[guild_id]
		db = guild_entry["db"]
		doc = db["quests"].find_one(
			{
				"guild_id": guild_id,
				"quest_id.value": str(quest_id),
			}
		)
		if doc is None:
			doc = db["quests"].find_one(
				{
					"quest_id.value": str(quest_id),
				}
			)
			if doc is None:
				return None
		return self.quest_from_doc(guild_id, doc)

	async def quest_id_autocomplete(
		self, interaction: discord.Interaction, current: str
	) -> list[discord.app_commands.Choice[str]]:
		if interaction.guild is None:
			return []
		await self.ensure_guild_cache(interaction.guild)
		db = self.bot.guild_data[interaction.guild.id]["db"]
		cursor = (
			db["quests"]
			.find(
				{
					"$or": [
						{"guild_id": interaction.guild.id},
						{"guild_id": {"$exists": False}},
					]
				},
				{"_id": 0, "quest_id": 1, "title": 1, "starting_at": 1},
			)
			.sort("starting_at", -1)
			.limit(20)
		)
		choices: list[discord.app_commands.Choice[str]] = []
		term = (current or "").upper()
		for doc in cursor:
			qid = doc.get("quest_id", {})
			if isinstance(qid, dict):
				label = qid.get("value") or f"{qid.get('prefix', 'QUES')}{qid.get('number', '')}"
			else:
				label = str(qid)
			if term and term not in label:
				continue
			title = doc.get("title") or label
			choices.append(discord.app_commands.Choice(name=f"{label} — {title}", value=label))
		return choices[:25]

	async def character_id_autocomplete(
		self, interaction: discord.Interaction, current: str
	) -> list[discord.app_commands.Choice[str]]:
		if interaction.guild is None or not isinstance(
			interaction.user, discord.Member
		):
			return []
		await self.ensure_guild_cache(interaction.guild)
		db = self.bot.guild_data[interaction.guild.id]["db"]
		cursor = (
			db["characters"]
			.find(
				{
					"guild_id": interaction.guild.id,
					"owner_id.value": str(UserID.from_body(str(interaction.user.id))),
				},
				{"_id": 0, "character_id": 1, "name": 1},
			)
			.limit(20)
		)
		term = (current or "").upper()
		choices: list[discord.app_commands.Choice[str]] = []
		for doc in cursor:
			cid = doc.get("character_id", {})
			if isinstance(cid, dict):
				label = cid.get("value") or f"{cid.get('prefix', 'CHAR')}{cid.get('number', '')}"
			else:
				label = str(cid)
			if term and term not in label:
				continue
			name = doc.get("name") or label
			choices.append(discord.app_commands.Choice(name=f"{label} — {name}", value=label))
		return choices[:25]

	# ------------------------------------------------------------------
	# API error helpers

	@staticmethod
	def normalize_signup_error(message: str) -> str:
		if "already signed up" in message.lower():
			return "You already requested to join this quest."
		return message

	@staticmethod
	def extract_api_detail(raw: str) -> Optional[str]:
		raw = (raw or "").strip()
		if not raw:
			return None
		try:
			data = json.loads(raw)
		except json.JSONDecodeError:
			return raw
		if isinstance(data, dict):
			detail = data.get("detail")
			if isinstance(detail, list) and detail:
				first = detail[0]
				if isinstance(first, dict):
					return str(first.get("msg") or raw)
				return str(first)
			if isinstance(detail, dict):
				return str(detail.get("msg") or detail)
			if detail is not None:
				return str(detail)
		return raw

	# ------------------------------------------------------------------
	# High-level quest flows

	async def approve_forge_draft(
		self,
		interaction: discord.Interaction,
		*,
		draft: ForgeDraft,
		author: discord.Member,
		source_message: discord.Message,
	) -> Optional[str]:
		guild = interaction.guild
		if guild is None:
			return None

		board_channel = await self.resolve_board_channel(
			guild, fallback=source_message.channel
		)

		quest_id = self.next_quest_id(guild.id)

		quest = Quest(
			quest_id=quest_id,
			guild_id=guild.id,
			referee_id=UserID.from_body(str(author.id)),
			channel_id=str(board_channel.id),
			message_id="0",
			raw=draft.raw,
			title=draft.title,
			description=draft.description,
			starting_at=draft.starting_at,
			duration=draft.duration,
			image_url=draft.image_url,
			status=QuestStatus.ANNOUNCED,
		)

		try:
			quest.validate_quest()
		except ValueError as exc:
			raise ValueError(f"Quest validation failed: {exc}")

		embed = self.build_draft_embed(
			draft,
			quest_id=str(quest_id),
			referee_display=author.mention,
			status=QuestStatus.ANNOUNCED,
		)

		from app.bot.quest.views import QuestSignupView

		announcement = await board_channel.send(
			content=f"{author.mention} scheduled a quest!",
			embed=embed,
			view=QuestSignupView(self, str(quest_id)),
		)

		quest.message_id = str(announcement.id)
		quest.channel_id = str(announcement.channel.id)
		persisted_via_api = await self.persist_quest_via_api(guild, quest)
		if not persisted_via_api:
			self.persist_quest(guild.id, quest)

		await self.cleanup_forge_preview(guild, source_message.id)

		try:
			await source_message.edit(view=None)
		except Exception:
			pass

		await send_demo_log(
			self.bot,
			guild,
			f"Quest `{quest.quest_id}` approved by {author.mention} in {board_channel.mention}",
		)

		return (
			f"Quest `{quest.quest_id}` announced in {announcement.channel.mention}."
		)

	async def discard_forge_draft(
		self,
		interaction: discord.Interaction,
		*,
		source_message: discord.Message,
	) -> None:
		if interaction.guild is None:
			return

		await self.cleanup_forge_preview(interaction.guild, source_message.id)

		try:
			await source_message.edit(view=None)
		except Exception:
			pass

	async def sync_quest_announcement(
		self,
		guild: discord.Guild,
		quest: Quest,
		*,
		approved_by_display: Optional[str] = None,
		last_updated_at: Optional[datetime] = None,
		view: Optional[discord.ui.View] = None,
	) -> None:
		channel = guild.get_channel(int(quest.channel_id))
		if channel is None:
			try:
				channel = await guild.fetch_channel(int(quest.channel_id))
			except Exception as exc:  # pragma: no cover - defensive log
				logging.debug(
					"Unable to resolve quest channel %s in guild %s: %s",
					quest.channel_id,
					guild.id,
					exc,
				)
				return

		try:
			message = await channel.fetch_message(int(quest.message_id))
		except Exception as exc:  # pragma: no cover - defensive log
			logging.debug(
				"Unable to fetch quest message %s in guild %s: %s",
				quest.message_id,
				guild.id,
				exc,
			)
			return

		embed = self.build_quest_embed(
			quest,
			guild,
			approved_by_display=approved_by_display,
			last_updated_at=last_updated_at,
		)

		try:
			resolved_view = view
			if resolved_view is None and quest.is_signup_open:
				from app.bot.quest.views import QuestSignupView

				resolved_view = QuestSignupView(self, str(quest.quest_id))
			await message.edit(embed=embed, view=resolved_view)
		except Exception as exc:  # pragma: no cover - defensive log
			logging.debug(
				"Unable to update quest announcement %s in guild %s: %s",
				quest.quest_id,
				guild.id,
				exc,
			)

	async def execute_nudge(
		self,
		interaction: discord.Interaction,
		quest_id: QuestID,
	) -> str:
		guild = interaction.guild
		if guild is None:
			raise ValueError("This action must be performed inside a guild.")

		member = interaction.user
		if not isinstance(member, discord.Member):
			raise ValueError("Only guild members can nudge quests.")

		user = await self.get_cached_user(member)
		if not user.is_referee:
			raise ValueError("Only referees can nudge quests.")

		quest = self.fetch_quest(guild.id, quest_id)
		if quest is None:
			raise ValueError("Quest not found.")

		if quest.referee_id != user.user_id:
			raise ValueError("Only the quest's referee can nudge this quest.")

		now = datetime.now(timezone.utc)
		cooldown = timedelta(hours=48)
		last_nudged_at = quest.last_nudged_at
		if last_nudged_at is not None:
			if last_nudged_at.tzinfo is None or last_nudged_at.tzinfo.utcoffset(last_nudged_at) is None:
				last_nudged_at = last_nudged_at.replace(tzinfo=timezone.utc)
			elapsed = now - last_nudged_at
			if elapsed < cooldown:
				remaining = cooldown - elapsed
				total_seconds = int(remaining.total_seconds())
				hours, remainder = divmod(total_seconds, 3600)
				minutes = remainder // 60
				parts: list[str] = []
				if hours:
					parts.append(f"{hours}h")
				if minutes:
					parts.append(f"{minutes}m")
				if not parts:
					parts.append("less than a minute")
				raise ValueError(
					"Nudge on cooldown. Try again in {}.".format(" ".join(parts))
				)

		try:
			via_api, api_timestamp = await self.nudge_via_api(guild, quest, user)
		except ValueError as exc:
			raise ValueError(str(exc)) from exc

		nudge_timestamp = now
		if via_api:
			refreshed = self.fetch_quest(guild.id, quest_id)
			if refreshed is not None:
				quest = refreshed
				nudge_timestamp = quest.last_nudged_at or now
			elif api_timestamp is not None:
				quest.last_nudged_at = api_timestamp
				nudge_timestamp = api_timestamp
			else:
				quest.last_nudged_at = now
				nudge_timestamp = now
		else:
			quest.last_nudged_at = now
			self.persist_quest(guild.id, quest)

		channel: Optional[Messageable] = None
		try:
			channel = guild.get_channel(int(quest.channel_id))
			if channel is None:
				channel = await guild.fetch_channel(int(quest.channel_id))
		except Exception:
			channel = None

		jump_url = f"https://discord.com/channels/{guild.id}/{quest.channel_id}/{quest.message_id}"
		quest_title = quest.title or str(quest.quest_id)
		if isinstance(channel, discord.TextChannel):
			try:
				embed = self.build_nudge_embed(
					quest,
					member,
					jump_url,
					bumped_at=nudge_timestamp,
				)
				await channel.send(embed=embed)
			except Exception:
				pass

		await self.sync_quest_announcement(
			guild,
			quest,
			last_updated_at=nudge_timestamp if isinstance(nudge_timestamp, datetime) else now,
		)

		await self.emit_nudge_log(guild, member, quest_title)

		channel_display = getattr(channel, "mention", None) if channel else None
		next_reference = nudge_timestamp if isinstance(nudge_timestamp, datetime) else now
		if next_reference.tzinfo is None or next_reference.tzinfo.utcoffset(next_reference) is None:
			next_reference = next_reference.replace(tzinfo=timezone.utc)
		relative_epoch = int((next_reference + cooldown).timestamp())
		relative_tag = f"<t:{relative_epoch}:R>"
		if channel_display:
			return f"Quest bumped in {channel_display}. Next nudge available {relative_tag}."
		return f"Quest bumped. Next nudge available {relative_tag}."

	async def execute_join(
		self,
		interaction: discord.Interaction,
		quest_id: QuestID,
		character_id: CharacterID,
	) -> str:
		guild = interaction.guild
		if guild is None:
			raise ValueError("This action must be performed inside a guild.")

		member = interaction.user
		if not isinstance(member, discord.Member):
			raise ValueError("Only guild members can join quests.")

		user = await self.get_cached_user(member)

		if not user.is_player:
			raise ValueError(
				"You need the PLAYER role to join quests. Use `/character create` first."
			)

		if not user.is_character_owner(character_id):
			raise ValueError("You can only join with characters you own.")

		quest = self.fetch_quest(guild.id, quest_id)
		if quest is None:
			raise ValueError("Quest not found.")

		if not quest.is_signup_open:
			raise ValueError("Signups are closed for this quest.")

		try:
			persisted_via_api = await self.add_signup_via_api(
				guild, quest, user, character_id
			)
		except ValueError as exc:
			raise ValueError(str(exc)) from exc

		if not persisted_via_api:
			try:
				quest.add_signup(user.user_id, character_id)
			except ValueError as exc:
				message = self.normalize_signup_error(str(exc))
				raise ValueError(message) from exc

			self.persist_quest(guild.id, quest)
		else:
			refreshed = self.fetch_quest(guild.id, quest_id)
			if refreshed is not None:
				quest = refreshed

		await self.sync_quest_announcement(
			guild,
			quest,
			last_updated_at=datetime.now(timezone.utc),
		)

		await send_demo_log(
			self.bot,
			guild,
			f"{member.mention} requested to join `{quest.title or quest.quest_id}` with `{str(character_id)}`",
		)

		return (
			f"Signup request submitted for `{str(quest_id)}` with `{str(character_id)}`. The referee will review it soon."
		)

	async def execute_leave(
		self,
		interaction: discord.Interaction,
		quest_id: QuestID,
	) -> str:
		guild = interaction.guild
		if guild is None:
			raise ValueError("This action must be performed inside a guild.")

		member = interaction.user
		if not isinstance(member, discord.Member):
			raise ValueError("Only guild members can leave quests.")

		quest = self.fetch_quest(guild.id, quest_id)
		if quest is None:
			raise ValueError("Quest not found.")

		user_id = UserID.from_body(str(member.id))

		try:
			removed_via_api = await self.remove_signup_via_api(guild, quest, user_id)
		except ValueError as exc:
			raise ValueError(str(exc)) from exc

		if not removed_via_api:
			try:
				quest.remove_signup(user_id)
			except ValueError as exc:
				raise ValueError(str(exc)) from exc
			self.persist_quest(guild.id, quest)
		else:
			refreshed = self.fetch_quest(guild.id, quest_id)
			if refreshed is not None:
				quest = refreshed

		await self.sync_quest_announcement(
			guild,
			quest,
			last_updated_at=datetime.now(timezone.utc),
		)

		channel = guild.get_channel(int(quest.channel_id))
		if channel is None:
			try:
				channel = await guild.fetch_channel(int(quest.channel_id))
			except Exception as exc:  # pragma: no cover - best effort logging
				logging.debug(
					"Unable to fetch quest channel %s in guild %s: %s",
					quest.channel_id,
					guild.id,
					exc,
				)
				channel = None

		if isinstance(channel, discord.TextChannel):
			await channel.send(
				f"{member.mention} withdrew from quest `{quest.title or quest.quest_id}`."
			)

		await send_demo_log(
			self.bot,
			guild,
			f"{member.mention} withdrew from quest `{quest.title or quest.quest_id}`",
		)

		return f"You have been removed from quest `{quest_id}`."

	async def remove_signup_view(self, guild: discord.Guild, quest: Quest) -> None:
		try:
			channel = guild.get_channel(int(quest.channel_id))
			if channel is None:
				channel = await guild.fetch_channel(int(quest.channel_id))
			message = await channel.fetch_message(int(quest.message_id))
			await message.edit(view=None)
		except Exception as exc:  # pragma: no cover - best effort cleanup
			logging.debug(
				"Unable to remove signup view for quest %s in guild %s: %s",
				quest.quest_id,
				guild.id,
				exc,
			)

	async def send_summary_reminders(self, guild: discord.Guild, quest: Quest) -> None:
		if not quest.signups:
			return

		for signup in quest.signups:
			member = await self.resolve_member_for_user_id(guild, signup.user_id)
			if member is None:
				continue

			user_record = (
				self.bot.guild_data.get(guild.id, {})
				.get("users", {})
				.get(member.id)
			)
			if user_record is not None and not getattr(user_record, "dm_opt_in", True):
				continue

			try:
				await member.send(
					f"Thanks for playing `{quest.title or quest.quest_id}`! "
					"Don't forget to submit your quest summary for bonus rewards."
				)
			except Exception as exc:  # pragma: no cover - DM failures expected
				logging.debug(
					"Unable to DM summary reminder to user %s in guild %s: %s",
					member.id,
					guild.id,
					exc,
				)

		await send_demo_log(
			self.bot,
			guild,
			f"Summary reminders sent for quest `{quest.title or quest.quest_id}`",
		)

	async def create_quest(
		self,
		interaction: discord.Interaction,
		*,
		title: str,
		description: Optional[str],
		start_time: datetime,
		duration: timedelta,
		image_url: Optional[str],
	) -> Quest:
		if interaction.guild is None or interaction.channel is None:
			raise ValueError("This command can only be used inside a guild text channel.")

		member = interaction.user
		if not isinstance(member, discord.Member):
			raise ValueError("Only guild members can create quests.")

		try:
			user = await self.get_cached_user(member)
		except RuntimeError as exc:
			raise RuntimeError(f"Failed to resolve user: {exc}")

		if not user.is_referee:
			raise ValueError("You need the REFEREE role to create quests.")

		quest_id = self.next_quest_id(interaction.guild.id)
		raw_markdown = f"## {title}\n\n{description or 'No description provided.'}"

		quest = Quest(
			quest_id=quest_id,
			guild_id=interaction.guild.id,
			referee_id=user.user_id,
			channel_id=str(interaction.channel.id),
			message_id="",
			raw=raw_markdown,
			title=title,
			description=description,
			starting_at=start_time,
			duration=duration,
			image_url=image_url,
		)

		quest.validate_quest()

		embed = self.build_quest_embed(
			quest,
			interaction.guild,
			referee_display=member.mention,
			approved_by_display=member.mention,
		)

		from app.bot.quest.views import QuestSignupView

		announcement = await interaction.channel.send(
			content=f"{member.mention} scheduled a quest!",
			embed=embed,
			view=QuestSignupView(self, str(quest_id)),
		)

		quest.channel_id = str(announcement.channel.id)
		quest.message_id = str(announcement.id)

		self.persist_quest(interaction.guild.id, quest)
		logging.info(
			"Quest %s created by %s in guild %s",
			quest.quest_id,
			member.id,
			interaction.guild.id,
		)

		await send_demo_log(
			self.bot,
			interaction.guild,
			f"Quest `{quest.quest_id}` created by {member.mention} in {interaction.channel.mention}",
		)

		return quest

	async def start_quest(
		self,
		interaction: discord.Interaction,
		quest: Quest,
	) -> None:
		if interaction.guild is None:
			raise ValueError("This command can only be used inside a guild.")

		member = interaction.user
		if not isinstance(member, discord.Member):
			raise ValueError("Only guild members can start quests.")

		referee_user_id = self.parse_entity_id(UserID, quest.referee_id)
		invoker_user_id = UserID.from_body(str(member.id))

		if referee_user_id != invoker_user_id:
			raise ValueError("Only the quest referee can start the quest.")

		quest.close_signups()
		quest.started_at = datetime.now(timezone.utc)

		self.persist_quest(interaction.guild.id, quest)

		await self.sync_quest_announcement(
			interaction.guild,
			quest,
			last_updated_at=quest.started_at,
			view=None,
		)
		logging.info(
			"Quest %s started by %s in guild %s",
			quest.quest_id,
			member.id,
			interaction.guild.id,
		)

		await self.remove_signup_view(interaction.guild, quest)

		channel = interaction.guild.get_channel(int(quest.channel_id))
		if isinstance(channel, discord.TextChannel):
			await channel.send(
				f"Quest `{quest.title or quest.quest_id}` has started! Signups are now closed."
			)

		await send_demo_log(
			self.bot,
			interaction.guild,
			f"Quest `{quest.title or quest.quest_id}` started by {member.mention}",
		)

	async def end_quest(
		self,
		interaction: discord.Interaction,
		quest: Quest,
	) -> None:
		if interaction.guild is None:
			raise ValueError("This command can only be used inside a guild.")

		member = interaction.user
		if not isinstance(member, discord.Member):
			raise ValueError("Only guild members can end quests.")

		referee_user_id = self.parse_entity_id(UserID, quest.referee_id)
		invoker_user_id = UserID.from_body(str(member.id))

		if referee_user_id != invoker_user_id:
			raise ValueError("Only the quest referee can end the quest.")

		quest.set_completed()
		quest.ended_at = datetime.now(timezone.utc)

		self.persist_quest(interaction.guild.id, quest)

		await self.sync_quest_announcement(
			interaction.guild,
			quest,
			last_updated_at=quest.ended_at,
			view=None,
		)
		logging.info(
			"Quest %s ended by %s in guild %s",
			quest.quest_id,
			member.id,
			interaction.guild.id,
		)

		await self.remove_signup_view(interaction.guild, quest)

		channel = interaction.guild.get_channel(int(quest.channel_id))
		if isinstance(channel, discord.TextChannel):
			await channel.send(
				f"Quest `{quest.title or quest.quest_id}` has been marked as completed. Please submit your summaries!"
			)

		await send_demo_log(
			self.bot,
			interaction.guild,
			f"Quest `{quest.title or quest.quest_id}` completed by {member.mention}",
		)

		await self.send_summary_reminders(interaction.guild, quest)

	# ------------------------------------------------------------------
	# Forge listener entry point

	async def handle_forge_message(self, message: discord.Message) -> None:
		if message.author.bot:
			return

		if message.guild is None:
			return

		if not self.is_forge_channel(message.channel):
			return

		if not isinstance(message.author, discord.Member):
			return

		try:
			user = await self.get_cached_user(message.author)
		except Exception:
			return

		if not user.is_referee:
			return

		if message.components:
			return

		from app.bot.quest.views import ForgeDraftView

		view = ForgeDraftView(self, message)
		try:
			await message.edit(view=view)
			logging.info(
				"Attached forge view to message %s in guild %s channel %s",
				message.id,
				message.guild.id,
				message.channel.id,
			)
		except Exception as exc:
			logging.debug(
				"Unable to attach forge view for message %s in guild %s: %s",
				message.id,
				message.guild.id,
				exc,
			)
