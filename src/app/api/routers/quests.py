from datetime import timedelta
from fastapi import APIRouter, HTTPException, Request

from app.domain.models.EntityIDModel import UserID, QuestID, CharacterID
from app.domain.usecase.unit import quest_unit
from app.api.schemas import Quest as APIQuest, QuestIn as APIQuestIn
from app.api.mappers import quest_to_api

router = APIRouter(prefix="/v1/quests", tags=["Quests"])

def _repos(req: Request):
    return req.app.state  # users_repo, chars_repo, quests_repo, summaries_repo

@router.post(
    "",
    response_model=APIQuest,
    status_code=201,
    response_model_exclude_none=True,
)
def create_quest(
    request: Request,
    body: APIQuestIn,
    channel_id: str | None = None,   # taken from query since not in QuestIn
    message_id: str | None = None,   # taken from query since not in QuestIn
):
    # Domain requires channel_id, message_id, raw for creation
    if not (channel_id and message_id and body.raw):
        raise HTTPException(
            status_code=400,
            detail="channel_id, message_id and raw are required for quest creation",
        )
    try:
        q = quest_unit.create_quest(
            quest_repo=_repos(request).quests_repo,
            users_repo=_repos(request).users_repo,
            referee_id=UserID.parse(body.referee_id) if body.referee_id else None,
            channel_id=channel_id,
            message_id=message_id,
            raw=body.raw,
            title=body.title,
            description=body.description,
            starting_at=body.starting_at,
            duration=(
                timedelta(hours=body.duration_hours)
                if body.duration_hours is not None else None
            ),
            image_url=body.image_url,
        )
        return quest_to_api(q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/{quest_id}",
    response_model=APIQuest,
    response_model_exclude_none=True,
)
def get_quest(request: Request, quest_id: str):
    try:
        q = quest_unit.get_quest(_repos(request).quests_repo, QuestID.parse(quest_id))
        return quest_to_api(q)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch(
    "/{quest_id}",
    response_model=APIQuest,
    response_model_exclude_none=True,
)
def patch_quest(request: Request, quest_id: str, body: APIQuestIn):
    patch = body.model_dump(exclude_unset=True)
    try:
        q = quest_unit.update_quest(
            quest_repo=_repos(request).quests_repo,
            quest_id=QuestID.parse(quest_id),
            title=patch.get("title"),
            description=patch.get("description"),
            starting_at=patch.get("starting_at"),
            duration=(
                timedelta(hours=patch["duration_hours"])
                if "duration_hours" in patch else None
            ),
            image_url=patch.get("image_url"),
        )
        return quest_to_api(q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{quest_id}", status_code=204)
def delete_quest(request: Request, quest_id: str):
    try:
        quest_unit.delete_quest(_repos(request).quests_repo, QuestID.parse(quest_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# --- Signups ---
@router.post(
    "/{quest_id}/signups",
    response_model=APIQuest,
    response_model_exclude_none=True,
)
def add_signup(request: Request, quest_id: str, payload: dict):
    try:
        user_id = UserID.parse(payload["user_id"])         # required
        char_id = CharacterID.parse(payload["character_id"])  # required
        q = quest_unit.add_player_signup(
            _repos(request).quests_repo,
            _repos(request).users_repo,
            _repos(request).chars_repo,
            QuestID.parse(quest_id),
            user_id,
            char_id,
        )
        return quest_to_api(q)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/{quest_id}/signups/{user_id}",
    response_model=APIQuest,
    response_model_exclude_none=True,
)
def remove_signup(request: Request, quest_id: str, user_id: str):
    try:
        q = quest_unit.remove_player_signup(
            _repos(request).quests_repo,
            _repos(request).users_repo,
            QuestID.parse(quest_id),
            UserID.parse(user_id),
        )
        return quest_to_api(q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{quest_id}/signups/{user_id}:select",
    response_model=APIQuest,
    response_model_exclude_none=True,
)
def select_signup(request: Request, quest_id: str, user_id: str):
    try:
        q = quest_unit.select_player_signup(
            _repos(request).quests_repo,
            _repos(request).users_repo,
            QuestID.parse(quest_id),
            UserID.parse(user_id),
        )
        return quest_to_api(q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Lifecycle commands ---
@router.post(
    "/{quest_id}:closeSignups",
    response_model=APIQuest,
    response_model_exclude_none=True,
)
def close_signups(request: Request, quest_id: str):
    try:
        q = quest_unit.close_quest_signups(_repos(request).quests_repo, QuestID.parse(quest_id))
        return quest_to_api(q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{quest_id}:setCompleted",
    response_model=APIQuest,
    response_model_exclude_none=True,
)
def set_completed(request: Request, quest_id: str):
    try:
        q = quest_unit.set_quest_completed(_repos(request).quests_repo, QuestID.parse(quest_id))
        return quest_to_api(q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{quest_id}:setCancelled",
    response_model=APIQuest,
    response_model_exclude_none=True,
)
def set_cancelled(request: Request, quest_id: str):
    try:
        q = quest_unit.set_quest_cancelled(_repos(request).quests_repo, QuestID.parse(quest_id))
        return quest_to_api(q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/{quest_id}:setAnnounced",
    response_model=APIQuest,
    response_model_exclude_none=True,
)
def set_announced(request: Request, quest_id: str):
    try:
        q = quest_unit.set_quest_announced(_repos(request).quests_repo, QuestID.parse(quest_id))
        return quest_to_api(q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
