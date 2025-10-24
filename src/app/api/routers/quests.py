from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.api.mappers import quest_to_api
from app.api.schemas import Quest as APIQuest
from app.api.schemas import QuestIn as APIQuestIn
from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID
from app.domain.models.QuestModel import Quest, QuestStatus
from app.domain.models.UserModel import User
from app.infra.mongo.characters_repo import CharactersRepoMongo
from app.infra.mongo.quests_repo import QuestsRepoMongo
from app.infra.mongo.users_repo import UsersRepoMongo

router = APIRouter(prefix="/v1/guilds/{guild_id}/quests", tags=["quests"])

quests_repo = QuestsRepoMongo()
users_repo = UsersRepoMongo()
characters_repo = CharactersRepoMongo()


def _coerce_starting_at(dt: Optional[datetime]) -> Optional[datetime]:
	if dt is None:
		return None
	if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
		return dt
	return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _duration_from_hours(hours: Optional[int]) -> Optional[timedelta]:
	if hours is None:
		return None
	return timedelta(hours=hours)


def _parse_quest_ids(values: Optional[List[str]]) -> List[QuestID]:
	parsed: List[QuestID] = []
	for value in values or []:
		try:
			parsed.append(QuestID.parse(value))
		except ValueError as exc:
			raise HTTPException(status_code=400, detail=str(exc))
	return parsed


def _parse_summary_ids(values: Optional[List[str]]) -> List[SummaryID]:
	parsed: List[SummaryID] = []
	for value in values or []:
		try:
			parsed.append(SummaryID.parse(value))
		except ValueError as exc:
			raise HTTPException(status_code=400, detail=str(exc))
	return parsed


async def _resolve_quest_id(guild_id: int, provided: Optional[str]) -> QuestID:
	if provided:
		try:
			return QuestID.parse(provided)
		except ValueError as exc:
			raise HTTPException(status_code=400, detail=str(exc))
	raw = await quests_repo.next_id(guild_id)
	return QuestID.parse(raw if isinstance(raw, str) else str(raw))


async def _ensure_referee(guild_id: int, referee_id_raw: Optional[str]) -> User:
	if not referee_id_raw:
		raise HTTPException(status_code=400, detail="referee_id is required")
	try:
		referee_id = UserID.parse(referee_id_raw)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc))
	referee = await users_repo.get(guild_id, str(referee_id))
	if referee is None or not referee.is_referee:
		raise HTTPException(
			status_code=400, detail="Referee not found or lacks permissions"
		)
	referee.guild_id = guild_id
	return referee


async def _ensure_user(guild_id: int, user_id: UserID) -> User:
	user = await users_repo.get(guild_id, str(user_id))
	if user is None:
		raise HTTPException(status_code=404, detail="User not found")
	user.guild_id = guild_id
	return user


async def _require_quest(guild_id: int, quest_id: str) -> Quest:
	quest = await quests_repo.get(guild_id, quest_id)
	if quest is None:
		raise HTTPException(status_code=404, detail="Quest not found")
	quest.guild_id = guild_id
	return quest


async def _persist_quest(guild_id: int, quest: Quest) -> APIQuest:
	quest.guild_id = guild_id
	quest.validate_quest()
	await quests_repo.upsert(guild_id, quest)
	return quest_to_api(quest)


@router.post("", response_model=APIQuest, status_code=201, response_model_exclude_none=True)
async def create_quest(
	guild_id: int,
	body: APIQuestIn,
	channel_id: Optional[str] = None,
	message_id: Optional[str] = None,
) -> APIQuest:
	if not (channel_id and message_id and body.raw):
		raise HTTPException(
			status_code=400,
			detail="channel_id, message_id and raw are required for quest creation",
		)

	quest_id = await _resolve_quest_id(guild_id, body.quest_id)
	referee = await _ensure_referee(guild_id, body.referee_id)

	quest = Quest(
		quest_id=quest_id,
		guild_id=guild_id,
		referee_id=referee.user_id,
		channel_id=channel_id,
		message_id=message_id,
		raw=body.raw,
		title=body.title,
		description=body.description,
		starting_at=_coerce_starting_at(body.starting_at),
		duration=_duration_from_hours(body.duration_hours),
		image_url=body.image_url,
		linked_quests=_parse_quest_ids(body.linked_quests),
		linked_summaries=_parse_summary_ids(body.linked_summaries),
		status=QuestStatus.ANNOUNCED,
	)

	return await _persist_quest(guild_id, quest)


@router.get("/{quest_id}", response_model=APIQuest, response_model_exclude_none=True)
async def get_quest(guild_id: int, quest_id: str) -> APIQuest:
	quest = await _require_quest(guild_id, quest_id)
	return quest_to_api(quest)


@router.patch("/{quest_id}", response_model=APIQuest, response_model_exclude_none=True)
async def patch_quest(guild_id: int, quest_id: str, body: APIQuestIn) -> APIQuest:
	patch = body.model_dump(exclude_unset=True)
	quest = await _require_quest(guild_id, quest_id)

	if "title" in patch:
		quest.title = patch["title"]
	if "description" in patch:
		quest.description = patch["description"]
	if "starting_at" in patch:
		quest.starting_at = _coerce_starting_at(patch["starting_at"])
	if "duration_hours" in patch:
		quest.duration = _duration_from_hours(patch["duration_hours"])
	if "image_url" in patch:
		quest.image_url = patch["image_url"]
	if "linked_quests" in patch:
		quest.linked_quests = _parse_quest_ids(patch.get("linked_quests"))
	if "linked_summaries" in patch:
		quest.linked_summaries = _parse_summary_ids(patch.get("linked_summaries"))

	return await _persist_quest(guild_id, quest)


@router.delete("/{quest_id}", status_code=204)
async def delete_quest(guild_id: int, quest_id: str) -> None:
	deleted = await quests_repo.delete(guild_id, quest_id)
	if not deleted:
		raise HTTPException(status_code=404, detail="Quest not found")


@router.post(
	"/{quest_id}/signups",
	response_model=APIQuest,
	response_model_exclude_none=True,
)
async def add_signup(guild_id: int, quest_id: str, payload: dict) -> APIQuest:
	try:
		raw_user = payload["user_id"]
		raw_character = payload["character_id"]
	except KeyError as exc:
		raise HTTPException(status_code=400, detail=f"Missing field: {exc.args[0]}")

	try:
		user_id = UserID.parse(raw_user)
		character_id = CharacterID.parse(raw_character)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc))

	quest = await _require_quest(guild_id, quest_id)
	user = await _ensure_user(guild_id, user_id)
	if not user.is_player:
		raise HTTPException(status_code=400, detail="User is not a player")

	character = await characters_repo.get(guild_id, str(character_id))
	if character is None:
		raise HTTPException(status_code=404, detail="Character not found")

	if not user.is_character_owner(character_id):
		raise HTTPException(status_code=400, detail="Character does not belong to user")

	if not quest.is_signup_open:
		raise HTTPException(status_code=400, detail="Signups are closed for this quest")

	try:
		quest.add_signup(user_id, character_id)
	except ValueError as exc:
		message = str(exc)
		if "already signed up" in message.lower():
			message = "You already requested to join this quest."
		raise HTTPException(status_code=400, detail=message)

	return await _persist_quest(guild_id, quest)


@router.delete(
	"/{quest_id}/signups/{user_id}",
	response_model=APIQuest,
	response_model_exclude_none=True,
)
async def remove_signup(guild_id: int, quest_id: str, user_id: str) -> APIQuest:
	try:
		parsed_user = UserID.parse(user_id)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc))

	quest = await _require_quest(guild_id, quest_id)

	try:
		quest.remove_signup(parsed_user)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc))

	return await _persist_quest(guild_id, quest)


@router.post(
	"/{quest_id}/signups/{user_id}:select",
	response_model=APIQuest,
	response_model_exclude_none=True,
)
async def select_signup(guild_id: int, quest_id: str, user_id: str) -> APIQuest:
	try:
		parsed_user = UserID.parse(user_id)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc))

	quest = await _require_quest(guild_id, quest_id)

	try:
		quest.select_signup(parsed_user)
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc))

	return await _persist_quest(guild_id, quest)


@router.post(
	"/{quest_id}:nudge",
	response_model=APIQuest,
	response_model_exclude_none=True,
)
async def nudge_quest(guild_id: int, quest_id: str, payload: dict) -> APIQuest:
	try:
		referee_id_raw = payload["referee_id"]
	except KeyError:
		raise HTTPException(status_code=400, detail="Missing field: referee_id")

	referee = await _ensure_referee(guild_id, referee_id_raw)

	quest = await _require_quest(guild_id, quest_id)

	if quest.referee_id != referee.user_id:
		raise HTTPException(
			status_code=403, detail="Only the quest referee can nudge this quest."
		)

	cooldown = timedelta(hours=48)
	now = datetime.now(timezone.utc)
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
			parts = []
			if hours:
				parts.append(f"{hours}h")
			if minutes:
				parts.append(f"{minutes}m")
			if not parts:
				parts.append("less than a minute")
			raise HTTPException(
				status_code=400,
				detail=f"Nudge on cooldown. Try again in {' '.join(parts)}.",
			)

	quest.last_nudged_at = now
	quest.guild_id = guild_id
	await quests_repo.upsert(guild_id, quest)

	return quest_to_api(quest)


@router.post(
	"/{quest_id}:closeSignups",
	response_model=APIQuest,
	response_model_exclude_none=True,
)
async def close_signups(guild_id: int, quest_id: str) -> APIQuest:
	quest = await _require_quest(guild_id, quest_id)
	quest.close_signups()
	return await _persist_quest(guild_id, quest)


@router.post(
	"/{quest_id}:setCompleted",
	response_model=APIQuest,
	response_model_exclude_none=True,
)
async def set_completed(guild_id: int, quest_id: str) -> APIQuest:
	quest = await _require_quest(guild_id, quest_id)
	quest.set_completed()
	return await _persist_quest(guild_id, quest)


@router.post(
	"/{quest_id}:setCancelled",
	response_model=APIQuest,
	response_model_exclude_none=True,
)
async def set_cancelled(guild_id: int, quest_id: str) -> APIQuest:
	quest = await _require_quest(guild_id, quest_id)
	quest.set_cancelled()
	return await _persist_quest(guild_id, quest)


@router.post(
	"/{quest_id}:setAnnounced",
	response_model=APIQuest,
	response_model_exclude_none=True,
)
async def set_announced(guild_id: int, quest_id: str) -> APIQuest:
	quest = await _require_quest(guild_id, quest_id)
	quest.set_announced()
	return await _persist_quest(guild_id, quest)
