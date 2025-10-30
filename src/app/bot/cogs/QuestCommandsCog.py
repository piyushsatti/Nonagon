from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Type, Literal, Callable

import aiohttp
import discord
from discord import app_commands
from discord.abc import Messageable
from discord.ext import commands

from app.bot.config import (
    BOT_FLUSH_VIA_ADAPTER,
    QUEST_API_BASE_URL,
    QUEST_BOARD_CHANNEL_ID,
)
from app.bot.quest import build_nudge_embed, build_quest_embed
from app.bot.quest import commands as quest_commands
from app.bot.quest.views import QuestSignupView
from app.bot.services import guild_settings_store
from app.bot.utils.log_stream import send_demo_log
from app.domain.models.EntityIDModel import CharacterID, EntityID, QuestID, UserID
from app.domain.models.QuestModel import PlayerSignUp, PlayerStatus, Quest, QuestStatus
from app.domain.models.UserModel import User
from app.infra.mongo.guild_adapter import upsert_quest_sync
from app.infra.mongo.users_repo import UsersRepoMongo
from app.infra.serialization import to_bson


class QuestCommandsCog(commands.Cog):
    """Slash commands for quest lifecycle management."""

    quest = app_commands.Group(
        name="quest", description="Manage Nonagon quests."
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._demo_log = send_demo_log
        self._users_repo = UsersRepoMongo()
        self._active_quest_sessions: set[int] = set()
        self._quest_scheduler_task: Optional[asyncio.Task[None]] = None

    async def cog_load(self) -> None:
        if self._quest_scheduler_task is None:
            self._quest_scheduler_task = self.bot.loop.create_task(
                self._quest_schedule_loop()
            )

    async def cog_unload(self) -> None:
        task = self._quest_scheduler_task
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            self._quest_scheduler_task = None
        self._active_quest_sessions: set[int] = set()

    # ---------- Quest Embed Helpers ----------

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

    def _lookup_user_display(self, guild_id: int, user_id: UserID) -> str:
        return self.lookup_user_display(guild_id, user_id)

    def _format_signup_label(self, guild_id: int, signup: PlayerSignUp) -> str:
        user_display = self.lookup_user_display(guild_id, signup.user_id)
        return f"{user_display} — {str(signup.character_id)}"

    async def _resolve_board_channel(
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

    async def _announce_quest_now(
        self,
        guild: discord.Guild,
        quest: Quest,
        *,
        invoker: Optional[discord.Member],
        fallback_channel: Optional[discord.abc.Messageable],
    ) -> None:
        settings = guild_settings_store.fetch_settings(guild.id) or {}
        target_channel: Optional[discord.TextChannel] = None
        channel_id = settings.get("quest_commands_channel_id")
        if channel_id is not None:
            try:
                target_channel = guild.get_channel(int(channel_id))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                target_channel = None
        if target_channel is None:
            if isinstance(fallback_channel, discord.TextChannel):
                target_channel = fallback_channel
            elif isinstance(fallback_channel, discord.abc.Messageable):
                pass  # non-text fallback unsupported for announcements
        if target_channel is None:
            raise ValueError(
                "No quest announcement channel configured. Run `/setup quest` first."
            )

        me = guild.me
        if me is None or not target_channel.permissions_for(me).send_messages:
            raise ValueError(
                f"I need Send Messages permission in {target_channel.mention} before announcing."
            )

        referee_display = self._lookup_user_display(guild.id, quest.referee_id)
        content_parts: list[str] = []
        if invoker is not None:
            content_parts.append(invoker.mention)
        elif referee_display:
            content_parts.append(referee_display)

        ping_role: Optional[discord.Role] = None
        ping_role_id = settings.get("quest_ping_role_id")
        if ping_role_id is not None:
            try:
                ping_role = guild.get_role(int(ping_role_id))
            except (TypeError, ValueError):
                ping_role = None
        if ping_role is not None:
            content_parts.append(ping_role.mention)
        content = " ".join(part for part in content_parts if part).strip() or None

        quest.status = QuestStatus.ANNOUNCED
        quest.announce_at = None

        embed = build_quest_embed(
            quest,
            guild,
            lookup_user_display=self.lookup_user_display,
            referee_display=referee_display,
            approved_by_display=referee_display,
        )

        message = await target_channel.send(
            content=content,
            embed=embed,
            view=QuestSignupView(self, str(quest.quest_id)),
        )

        quest.channel_id = str(message.channel.id)
        quest.message_id = str(message.id)
        self._persist_quest(guild.id, quest)

        await send_demo_log(
            self.bot,
            guild,
            f"Quest `{quest.quest_id}` announced in {target_channel.mention}",
        )

    def _parse_datetime_input(self, value: str) -> Optional[datetime]:
        text = (value or "").strip()
        if not text:
            return None
        if text.isdigit():
            try:
                return datetime.fromtimestamp(int(text), tz=timezone.utc)
            except (OverflowError, ValueError):
                return None
        return None

    async def _sync_quest_announcement(
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

        embed = build_quest_embed(
            quest,
            guild,
            lookup_user_display=self.lookup_user_display,
            approved_by_display=approved_by_display,
            last_updated_at=last_updated_at,
        )

        try:
            resolved_view = view
            if resolved_view is None and quest.is_signup_open:
                resolved_view = QuestSignupView(self, str(quest.quest_id))
            await message.edit(embed=embed, view=resolved_view)
        except Exception as exc:  # pragma: no cover - defensive log
            logging.debug(
                "Unable to update quest announcement %s in guild %s: %s",
                quest.quest_id,
                guild.id,
                exc,
            )

    async def _ensure_guild_cache(self, guild: discord.Guild) -> None:
        if guild.id not in self.bot.guild_data:
            await self.bot.load_or_create_guild_cache(guild)

    async def _quest_schedule_loop(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._run_scheduled_announcements()
            except Exception:  # pragma: no cover - defensive
                logging.exception("Failed to process scheduled quest announcements")
            await asyncio.sleep(60)

    async def _run_scheduled_announcements(self) -> None:
        now = datetime.now(timezone.utc)
        for guild in list(self.bot.guilds):
            await self._ensure_guild_cache(guild)
            guild_entry = self.bot.guild_data.get(guild.id)
            if not guild_entry:
                continue
            db = guild_entry["db"]
            cursor = db["quests"].find(
                {
                    "guild_id": guild.id,
                    "announce_at": {"$lte": now},
                    "$or": [
                        {"channel_id": {"$exists": False}},
                        {"channel_id": None},
                        {"channel_id": ""},
                    ],
                },
            )
            for doc in cursor:
                try:
                    quest = self._quest_from_doc(guild.id, doc)
                except Exception:
                    logging.exception(
                        "Failed to deserialize quest doc for guild %s", guild.id
                    )
                    continue
                if quest.status not in (QuestStatus.DRAFT, QuestStatus.ANNOUNCED):
                    continue
                if quest.channel_id and quest.message_id:
                    continue
                try:
                    await self._announce_quest_now(
                        guild, quest, invoker=None, fallback_channel=None
                    )
                except Exception:
                    logging.exception(
                        "Scheduled announcement failed for quest %s in guild %s",
                        quest.quest_id,
                        guild.id,
                    )

    async def _get_cached_user(self, member: discord.Member) -> User:
        await self._ensure_guild_cache(member.guild)
        guild_entry = self.bot.guild_data[member.guild.id]

        user = guild_entry["users"].get(member.id)
        if user is not None:
            return user

        listener: Optional[commands.Cog] = self.bot.get_cog("ListnerCog")
        if listener is None:
            raise RuntimeError("Listener cog not loaded; cannot resolve users.")

        # Reuse listener helper to ensure cache consistency
        ensure_method = getattr(listener, "_ensure_cached_user", None)
        if ensure_method is None:
            raise RuntimeError("Listener cog missing _ensure_cached_user helper.")

        user = await ensure_method(member)  # type: ignore[misc]
        return user

    async def _resolve_member_for_user_id(
        self, guild: discord.Guild, user_id: UserID
    ) -> Optional[discord.Member]:
        await self._ensure_guild_cache(guild)
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

    def _parse_entity_id(
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
            return self._parse_entity_id(cls, fallback)
        raise ValueError(f"Unable to parse {cls.__name__} from payload={payload!r}")

    def _next_quest_id(self, guild_id: int) -> QuestID:
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

    def _quest_to_doc(self, quest: Quest) -> dict:
        doc = to_bson(quest)
        doc["guild_id"] = quest.guild_id
        return doc

    def _persist_quest(self, guild_id: int, quest: Quest) -> None:
        if BOT_FLUSH_VIA_ADAPTER:
            from app.bot.database import db_client

            upsert_quest_sync(db_client, guild_id, quest)
            return
        guild_entry = self.bot.guild_data[guild_id]
        db = guild_entry["db"]
        quest.guild_id = guild_id
        payload = self._quest_to_doc(quest)
        db["quests"].update_one(
            {"guild_id": guild_id, "quest_id.value": str(quest.quest_id)},
            {"$set": payload},
            upsert=True,
        )

    async def _persist_quest_via_api(self, guild: discord.Guild, quest: Quest) -> bool:
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
            payload["duration_hours"] = quest.duration.total_seconds() / 3600.0

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

    async def _add_signup_via_api(
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
                    detail = self._extract_api_detail(raw)

                    if resp.status in (400, 404):
                        message = self._normalize_signup_error(
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

    async def _select_signup_via_api(
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
                    detail = self._extract_api_detail(raw)

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

    async def _remove_signup_via_api(
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
                    detail = self._extract_api_detail(raw)

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

    async def _nudge_via_api(
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
                    detail = self._extract_api_detail(raw)

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

    async def _emit_nudge_log(
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

    async def _close_signups_via_api(
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
                    detail = self._extract_api_detail(raw)

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

    def _quest_from_doc(self, guild_id: int, doc: dict) -> Quest:
        quest_id_doc = doc.get("quest_id")
        ref_doc = doc.get("referee_id")
        stored_gid = doc.get("guild_id", guild_id)

        ref_payload = ref_doc if ref_doc else doc.get("referee")

        starting_at = doc.get("starting_at")
        if isinstance(starting_at, str):
            try:
                starting_at = datetime.fromisoformat(starting_at)
            except ValueError:
                starting_at = None
        if isinstance(starting_at, datetime):
            if starting_at.tzinfo is None or starting_at.tzinfo.utcoffset(starting_at) is None:
                starting_at = starting_at.replace(tzinfo=timezone.utc)

        duration = None
        if doc.get("duration") is not None:
            try:
                duration = timedelta(seconds=float(doc["duration"]))
            except (TypeError, ValueError):
                duration = None

        quest = Quest(
            quest_id=self._parse_entity_id(QuestID, quest_id_doc, fallback=doc.get("_id")),
            guild_id=int(stored_gid),
            referee_id=self._parse_entity_id(UserID, ref_payload),
            raw=doc.get("raw", ""),
            channel_id=doc.get("channel_id"),
            message_id=doc.get("message_id"),
            title=doc.get("title"),
            description=doc.get("description"),
            starting_at=starting_at,
            duration=duration,
            image_url=doc.get("image_url"),
        )

        status_value = doc.get("status")
        if status_value:
            quest.status = (
                status_value
                if isinstance(status_value, QuestStatus)
                else QuestStatus(status_value)
            )

        announce_at = doc.get("announce_at")
        if isinstance(announce_at, str):
            try:
                announce_at = datetime.fromisoformat(announce_at)
            except ValueError:
                announce_at = None
        if isinstance(announce_at, datetime):
            if announce_at.tzinfo is None or announce_at.tzinfo.utcoffset(announce_at) is None:
                announce_at = announce_at.replace(tzinfo=timezone.utc)
        quest.announce_at = announce_at

        quest.started_at = doc.get("started_at")
        if isinstance(quest.started_at, str):
            try:
                quest.started_at = datetime.fromisoformat(quest.started_at)
            except ValueError:
                quest.started_at = None
        if isinstance(quest.started_at, datetime):
            if quest.started_at.tzinfo is None or quest.started_at.tzinfo.utcoffset(quest.started_at) is None:
                quest.started_at = quest.started_at.replace(tzinfo=timezone.utc)

        quest.ended_at = doc.get("ended_at")
        if isinstance(quest.ended_at, str):
            try:
                quest.ended_at = datetime.fromisoformat(quest.ended_at)
            except ValueError:
                quest.ended_at = None
        if isinstance(quest.ended_at, datetime):
            if quest.ended_at.tzinfo is None or quest.ended_at.tzinfo.utcoffset(quest.ended_at) is None:
                quest.ended_at = quest.ended_at.replace(tzinfo=timezone.utc)

        quest.last_nudged_at = doc.get("last_nudged_at")
        if isinstance(quest.last_nudged_at, str):
            try:
                quest.last_nudged_at = datetime.fromisoformat(quest.last_nudged_at)
            except ValueError:
                quest.last_nudged_at = None
        if isinstance(quest.last_nudged_at, datetime):
            if quest.last_nudged_at.tzinfo is None or quest.last_nudged_at.tzinfo.utcoffset(quest.last_nudged_at) is None:
                quest.last_nudged_at = quest.last_nudged_at.replace(tzinfo=timezone.utc)

        signups: list[PlayerSignUp] = []
        for entry in doc.get("signups", []):
            uid = entry.get("user_id")
            cid = entry.get("character_id")
            status = entry.get("status")
            if uid is None or cid is None:
                continue
            user_id = self._parse_entity_id(UserID, uid)
            char_id = self._parse_entity_id(CharacterID, cid)
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

    def _fetch_quest(self, guild_id: int, quest_id: QuestID) -> Optional[Quest]:
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
        return self._quest_from_doc(guild_id, doc)

    async def quest_id_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild is None:
            return []
        await self._ensure_guild_cache(interaction.guild)
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
        choices: list[app_commands.Choice[str]] = []
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
            choices.append(app_commands.Choice(name=f"{label} — {title}", value=label))
        return choices[:25]

    async def character_id_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            return []
        await self._ensure_guild_cache(interaction.guild)
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
        choices: list[app_commands.Choice[str]] = []
        for doc in cursor:
            cid = doc.get("character_id", {})
            if isinstance(cid, dict):
                label = cid.get("value") or f"{cid.get('prefix', 'CHAR')}{cid.get('number', '')}"
            else:
                label = str(cid)
            if term and term not in label:
                continue
            name = doc.get("name") or label
            choices.append(app_commands.Choice(name=f"{label} — {name}", value=label))
        return choices[:25]

    @staticmethod
    def _normalize_signup_error(message: str) -> str:
        if "already signed up" in message.lower():
            return "You already requested to join this quest."
        return message

    @staticmethod
    def _extract_api_detail(raw: str) -> Optional[str]:
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

    async def _execute_nudge(
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

        user = await self._get_cached_user(member)
        if not user.is_referee:
            raise ValueError("Only referees can nudge quests.")

        quest = self._fetch_quest(guild.id, quest_id)
        if quest is None:
            raise ValueError("Quest not found.")

        if quest.referee_id != user.user_id:
            raise ValueError("Only the quest's referee can nudge this quest.")

        if not quest.channel_id or not quest.message_id:
            raise ValueError("Announce the quest before sending a nudge.")

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
            via_api, api_timestamp = await self._nudge_via_api(guild, quest, user)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        nudge_timestamp = now
        if via_api:
            refreshed = self._fetch_quest(guild.id, quest_id)
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
            self._persist_quest(guild.id, quest)

        channel: Optional[Messageable] = None
        try:
            channel = guild.get_channel(int(quest.channel_id))
            if channel is None:
                channel = await guild.fetch_channel(int(quest.channel_id))
        except Exception:
            channel = None

        settings = guild_settings_store.fetch_settings(guild.id) or {}
        ping_role: Optional[discord.Role] = None
        ping_role_id = settings.get("quest_ping_role_id")
        if ping_role_id is not None:
            try:
                ping_role = guild.get_role(int(ping_role_id))
            except (TypeError, ValueError):
                ping_role = None

        jump_url = f"https://discord.com/channels/{guild.id}/{quest.channel_id}/{quest.message_id}"
        quest_title = quest.title or str(quest.quest_id)
        if channel is not None:
            try:
                embed = build_nudge_embed(
                    quest,
                    member,
                    jump_url,
                    bumped_at=nudge_timestamp,
                )
                content = ping_role.mention if ping_role is not None else None
                await channel.send(content=content, embed=embed)
            except Exception:
                pass

        await self._sync_quest_announcement(
            guild,
            quest,
            last_updated_at=nudge_timestamp if isinstance(nudge_timestamp, datetime) else now,
        )

        await self._emit_nudge_log(guild, member, quest_title)

        channel_display = getattr(channel, "mention", None) if channel else None
        next_reference = nudge_timestamp if isinstance(nudge_timestamp, datetime) else now
        if next_reference.tzinfo is None or next_reference.tzinfo.utcoffset(next_reference) is None:
            next_reference = next_reference.replace(tzinfo=timezone.utc)
        relative_epoch = int((next_reference + cooldown).timestamp())
        relative_tag = f"<t:{relative_epoch}:R>"
        if channel_display:
            return f"Quest bumped in {channel_display}. Next nudge available {relative_tag}."
        return f"Quest bumped. Next nudge available {relative_tag}."

    async def _execute_join(
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

        user = await self._get_cached_user(member)

        if not user.is_player:
            raise ValueError(
                "You need the PLAYER role to join quests. Use `/character create` first."
            )

        if not user.is_character_owner(character_id):
            raise ValueError("You can only join with characters you own.")

        quest = self._fetch_quest(guild.id, quest_id)
        if quest is None:
            raise ValueError("Quest not found.")

        if not quest.is_signup_open:
            raise ValueError("Signups are closed for this quest.")

        try:
            persisted_via_api = await self._add_signup_via_api(
                guild, quest, user, character_id
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        if not persisted_via_api:
            try:
                quest.add_signup(user.user_id, character_id)
            except ValueError as exc:
                message = self._normalize_signup_error(str(exc))
                raise ValueError(message) from exc

            self._persist_quest(guild.id, quest)
        else:
            refreshed = self._fetch_quest(guild.id, quest_id)
            if refreshed is not None:
                quest = refreshed

        await self._sync_quest_announcement(
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

    async def _execute_leave(
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

        quest = self._fetch_quest(guild.id, quest_id)
        if quest is None:
            raise ValueError("Quest not found.")

        user_id = UserID.from_body(str(member.id))

        try:
            removed_via_api = await self._remove_signup_via_api(guild, quest, user_id)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        if not removed_via_api:
            try:
                quest.remove_signup(user_id)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
            self._persist_quest(guild.id, quest)
        else:
            refreshed = self._fetch_quest(guild.id, quest_id)
            if refreshed is not None:
                quest = refreshed

        await self._sync_quest_announcement(
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

        if channel is not None:
            await channel.send(
                f"{member.mention} withdrew from quest `{quest.title or quest.quest_id}`."
            )

        await send_demo_log(
            self.bot,
            guild,
            f"{member.mention} withdrew from quest `{quest.title or quest.quest_id}`",
        )

        return f"You have been removed from quest `{quest_id}`."

    async def _remove_signup_view(self, guild: discord.Guild, quest: Quest) -> None:
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

    async def _send_summary_reminders(self, guild: discord.Guild, quest: Quest) -> None:
        if not quest.signups:
            return

        for signup in quest.signups:
            member = await self._resolve_member_for_user_id(guild, signup.user_id)
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

    # ---------- Public helpers for quest views (legacy interface) ----------

    async def get_cached_user(self, member: discord.Member) -> User:
        return await self._get_cached_user(member)

    def fetch_quest(self, guild_id: int, quest_id: QuestID) -> Optional[Quest]:
        return self._fetch_quest(guild_id, quest_id)

    def format_signup_label(self, guild_id: int, signup: PlayerSignUp) -> str:
        return self._format_signup_label(guild_id, signup)

    def persist_quest(self, guild_id: int, quest: Quest) -> None:
        self._persist_quest(guild_id, quest)

    async def sync_quest_announcement(
        self,
        guild: discord.Guild,
        quest: Quest,
        *,
        approved_by_display: Optional[str] = None,
        last_updated_at: Optional[datetime] = None,
        view: Optional[discord.ui.View] = None,
    ) -> None:
        await self._sync_quest_announcement(
            guild,
            quest,
            approved_by_display=approved_by_display,
            last_updated_at=last_updated_at,
            view=view,
        )

    async def execute_join(
        self,
        interaction: discord.Interaction,
        quest_id: QuestID,
        character_id: CharacterID,
    ) -> str:
        return await self._execute_join(interaction, quest_id, character_id)

    async def execute_leave(
        self,
        interaction: discord.Interaction,
        quest_id: QuestID,
    ) -> str:
        return await self._execute_leave(interaction, quest_id)

    async def execute_nudge(
        self,
        interaction: discord.Interaction,
        quest_id: QuestID,
    ) -> str:
        return await self._execute_nudge(interaction, quest_id)

    async def select_signup_via_api(
        self,
        guild: discord.Guild,
        quest: Quest,
        user_id: UserID,
    ) -> bool:
        return await self._select_signup_via_api(guild, quest, user_id)

    async def remove_signup_via_api(
        self,
        guild: discord.Guild,
        quest: Quest,
        user_id: UserID,
    ) -> bool:
        return await self._remove_signup_via_api(guild, quest, user_id)

    async def close_signups_via_api(
        self,
        guild: discord.Guild,
        quest: Quest,
    ) -> bool:
        return await self._close_signups_via_api(guild, quest)

    async def resolve_member_for_user_id(
        self, guild: discord.Guild, user_id: UserID
    ) -> Optional[discord.Member]:
        return await self._resolve_member_for_user_id(guild, user_id)

    async def _ensure_dm_channel(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> Optional[Messageable]:
        try:
            return await member.create_dm()
        except discord.Forbidden:
            await interaction.followup.send(
                "I can't send you direct messages. Enable DMs from server members and run `/quest create` again.",
                ephemeral=True,
            )
            return None

    _SESSION_ERROR_HANDLERS: Dict[type[Exception], Callable[[Exception], str]] = {
        RuntimeError: lambda exc: str(exc),
        discord.HTTPException: lambda exc: (
            "Quest creation encountered a Discord error. Please try again later."
        ),
    }

    async def _handle_session_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        for exc_type, formatter in self._SESSION_ERROR_HANDLERS.items():
            if isinstance(error, exc_type):
                message = formatter(error)
                break
        else:
            logging.exception("Unexpected quest creation session error: %s", error)
            message = (
                "Quest creation encountered an unexpected error. Please try again later."
            )

        await interaction.followup.send(message, ephemeral=True)

    async def _run_quest_creation_session(
        self,
        session: "QuestCreationSession",
        interaction: discord.Interaction,
    ) -> Optional[Quest]:
        try:
            result = await session.run()
        except Exception as exc:
            await self._handle_session_error(interaction, exc)
            return None

        if not result.success or result.quest is None:
            await interaction.followup.send(
                result.error or "Quest creation cancelled.",
                ephemeral=True,
            )
            return None

        return result.quest

    async def _send_creation_summary(
        self,
        session: "QuestCreationSession",
        quest: Quest,
        dm_message: str,
    ) -> bool:
        try:
            await session.send_completion_summary(quest, dm_message)
            return True
        except RuntimeError:
            return False
        except Exception as exc:  # pragma: no cover - defensive logging
            logging.exception("Quest creation summary DM failed: %s", exc)
            return False

    @quest.command(name="create", description="Start a DM wizard to draft a quest.")
    @app_commands.guild_only()
    async def quest_create(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Only guild members can manage quests.", ephemeral=True
            )
            return

        try:
            user = await self._get_cached_user(member)
        except RuntimeError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        if not user.is_referee and not is_allowed_staff(self.bot, member):
            await interaction.response.send_message(
                "You need the REFEREE role or an allowed staff role to create quests.",
                ephemeral=True,
            )
            return

        if member.id in self._active_quest_sessions:
            await interaction.response.send_message(
                "You already have an active quest session. Complete or cancel it before starting a new one.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        self._active_quest_sessions.add(member.id)
        try:
            dm_channel = await self._ensure_dm_channel(interaction, member)
            if dm_channel is None:
                return

            session = QuestCreationSession(
                self, interaction.guild, member, user, dm_channel
            )
            quest = await self._run_quest_creation_session(session, interaction)
            if quest is None:
                return

            self._persist_quest(interaction.guild.id, quest)
            dm_message = (
                f"Quest `{quest.quest_id}` is saved as a draft.\n"
                f"Run `/quest announce` in the server with Quest ID `{quest.quest_id}` when you're ready to publish, "
                "or `/quest edit` to make further changes."
            )
            dm_sent = await self._send_creation_summary(session, quest, dm_message)

            reply = (
                f"Quest `{quest.quest_id}` drafted. "
                "Use `/quest announce` when you're ready to publish it."
            )
            if dm_sent:
                reply += " I sent you a DM with the preview and next steps."
            else:
                reply += " I couldn't DM you the preview—check your privacy settings."

            post_view = QuestAnnounceView(
                self,
                session,
                interaction.guild,
                member,
                quest,
            )
            await session._update_preview(
                quest,
                header=(
                    "**Quest Draft Saved**\n"
                    "Announce immediately or schedule an announcement using the buttons below."
                ),
                view=post_view,
            )

            await interaction.followup.send(reply, ephemeral=True)
        finally:
            self._active_quest_sessions.discard(member.id)

    @quest.command(name="announce", description="Announce a quest now or at a scheduled time.")
    @app_commands.describe(
        quest="Quest ID (e.g. QUESA1B2C3)",
        time="Optional ISO timestamp or epoch seconds for scheduled announce",
    )
    @app_commands.guild_only()
    async def quest_announce(
        self,
        interaction: discord.Interaction,
        quest: str,
        time: Optional[str] = None,
    ) -> None:
        await quest_commands.quest_announce(self, interaction, quest, time)

    @quest.command(name="nudge", description="Re-announce a quest to bring attention back to it.")
    @app_commands.describe(quest="Quest ID (e.g. QUESA1B2C3)")
    @app_commands.guild_only()
    async def quest_nudge(
        self, interaction: discord.Interaction, quest: str
    ) -> None:
        await quest_commands.quest_nudge(self, interaction, quest)

    @quest.command(name="cancel", description="Cancel a quest and remove its signup interface.")
    @app_commands.describe(quest="Quest ID (e.g. QUESA1B2C3)")
    @app_commands.guild_only()
    async def quest_cancel(
        self, interaction: discord.Interaction, quest: str
    ) -> None:
        await quest_commands.quest_cancel(self, interaction, quest)

    @quest.command(name="players", description="List players and characters who played in a quest.")
    @app_commands.describe(quest="Quest ID (e.g. QUESA1B2C3)")
    @app_commands.guild_only()
    async def quest_players(
        self, interaction: discord.Interaction, quest: str
    ) -> None:
        await quest_commands.quest_players(self, interaction, quest)

    @quest.command(name="edit", description="Update a drafted or announced quest via DM.")
    @app_commands.describe(quest="Quest ID (e.g. QUESA1B2C3)")
    @app_commands.guild_only()
    async def quest_edit(self, interaction: discord.Interaction, quest: str) -> None:
        await quest_commands.quest_edit(self, interaction, quest)

    @app_commands.command(
        name="joinquest",
        description="Join an announced quest with one of your characters.",
    )
    @app_commands.autocomplete(
        quest_id=quest_id_autocomplete, character_id=character_id_autocomplete
    )
    @app_commands.describe(
    quest_id="Quest identifier (e.g. QUESA1B2C3)",
        character_id="Character identifier (e.g. CHAR0001)",
    )
    async def joinquest(
        self,
        interaction: discord.Interaction,
        quest_id: str,
        character_id: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            quest_id_obj = QuestID.parse(quest_id.upper())
            char_id_obj = CharacterID.parse(character_id.upper())
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        try:
            message = await self._execute_join(interaction, quest_id_obj, char_id_obj)
        except RuntimeError as exc:
            logging.exception("Failed to resolve user for quest join: %s", exc)
            await interaction.followup.send(
                "Internal error resolving your profile; please try again later.",
                ephemeral=True,
            )
            return
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(
        name="leavequest", description="Withdraw from a quest signup."
    )
    @app_commands.autocomplete(quest_id=quest_id_autocomplete)
    @app_commands.describe(
    quest_id="Quest identifier (e.g. QUESA1B2C3)",
    )
    async def leavequest(
        self,
        interaction: discord.Interaction,
        quest_id: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            quest_id_obj = QuestID.parse(quest_id.upper())
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        try:
            message = await self._execute_leave(interaction, quest_id_obj)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(
        name="startquest", description="Close signups and mark a quest as started."
    )
    @app_commands.describe(quest_id="Quest identifier (e.g. QUESA1B2C3)")
    async def startquest(self, interaction: discord.Interaction, quest_id: str) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.followup.send(
                "Only guild members can start quests.", ephemeral=True
            )
            return

        try:
            quest_id_obj = QuestID.parse(quest_id.upper())
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        quest = self._fetch_quest(interaction.guild.id, quest_id_obj)
        if quest is None:
            await interaction.followup.send("Quest not found.", ephemeral=True)
            return

        try:
            referee_user_id = (
                quest.referee_id
                if isinstance(quest.referee_id, UserID)
                else UserID.parse(str(quest.referee_id))
            )
        except Exception:
            referee_user_id = None

        invoker_user_id = UserID.from_body(str(member.id))

        if referee_user_id != invoker_user_id:
            await interaction.followup.send(
                "Only the quest referee can start the quest.", ephemeral=True
            )
            return

        quest.close_signups()
        quest.started_at = datetime.now(timezone.utc)

        self._persist_quest(interaction.guild.id, quest)

        await self._sync_quest_announcement(
            interaction.guild,
            quest,
            last_updated_at=quest.started_at,
            view=None,
        )
        logging.info(
            "Quest %s started by %s in guild %s",
            quest_id_obj,
            member.id,
            interaction.guild.id,
        )

        await self._remove_signup_view(interaction.guild, quest)

        channel = interaction.guild.get_channel(int(quest.channel_id))
        if channel is not None:
            await channel.send(
                f"Quest `{quest.title or quest.quest_id}` has started! Signups are now closed."
            )

        await send_demo_log(
            self.bot,
            interaction.guild,
            f"Quest `{quest.title or quest.quest_id}` started by {member.mention}",
        )

        await interaction.followup.send(
            f"Quest `{quest_id_obj}` marked as started.", ephemeral=True
        )

    @app_commands.command(
        name="endquest",
        description="Mark a quest as completed and record the finish time.",
    )
    @app_commands.describe(quest_id="Quest identifier (e.g. QUESA1B2C3)")
    async def endquest(self, interaction: discord.Interaction, quest_id: str) -> None:
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            await interaction.followup.send(
                "This command can only be used inside a guild.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.followup.send(
                "Only guild members can end quests.", ephemeral=True
            )
            return

        try:
            quest_id_obj = QuestID.parse(quest_id.upper())
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        quest = self._fetch_quest(interaction.guild.id, quest_id_obj)
        if quest is None:
            await interaction.followup.send("Quest not found.", ephemeral=True)
            return

        try:
            referee_user_id = (
                quest.referee_id
                if isinstance(quest.referee_id, UserID)
                else UserID.parse(str(quest.referee_id))
            )
        except Exception:
            referee_user_id = None

        invoker_user_id = UserID.from_body(str(member.id))

        if referee_user_id != invoker_user_id:
            await interaction.followup.send(
                "Only the quest referee can end the quest.", ephemeral=True
            )
            return

        quest.set_completed()
        quest.ended_at = datetime.now(timezone.utc)

        self._persist_quest(interaction.guild.id, quest)

        await self._sync_quest_announcement(
            interaction.guild,
            quest,
            last_updated_at=quest.ended_at,
            view=None,
        )
        logging.info(
            "Quest %s ended by %s in guild %s",
            quest_id_obj,
            member.id,
            interaction.guild.id,
        )

        await self._remove_signup_view(interaction.guild, quest)

        channel = interaction.guild.get_channel(int(quest.channel_id))
        if channel is not None:
            await channel.send(
                f"Quest `{quest.title or quest.quest_id}` has been marked as completed. Please submit your summaries!"
            )

        await send_demo_log(
            self.bot,
            interaction.guild,
            f"Quest `{quest.title or quest.quest_id}` completed by {member.mention}",
        )

        await self._send_summary_reminders(interaction.guild, quest)

        await interaction.followup.send(
            f"Quest `{quest_id_obj}` marked as completed.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    cog = QuestCommandsCog(bot)
    await bot.add_cog(cog)
    bot.add_view(QuestSignupView(cog))
