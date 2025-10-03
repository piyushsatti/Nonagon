"""REST endpoints for orchestrating quest lifecycle and signups."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException

import app.api.deps as deps
from app.api.mappers import quest_to_api
from app.api.schemas import Quest, QuestCreate, QuestSignup, QuestUpdate
from app.domain.usecase import quests as quest_usecases

router = APIRouter(prefix="/v1/quests", tags=["Quests"])

quests_repo = deps.quests_repo
users_repo = deps.user_repo
chars_repo = deps.chars_repo


@router.post(
    "",
    response_model=Quest,
    status_code=201,
    response_model_exclude_none=True,
)
async def create_quest(body: QuestCreate) -> Quest:
    """Create a quest announcement from incoming Discord ingestion data."""
    try:
        usecase = quest_usecases.CreateQuest(
            quests_repo=quests_repo,
            users_repo=users_repo,
        )
        quest = await usecase.execute(
            referee_id=body.referee_id,
            channel_id=body.channel_id,
            message_id=body.message_id,
            raw=body.raw,
            title=body.title,
            description=body.description,
            starting_at=body.starting_at,
            duration=(
                timedelta(hours=body.duration_hours)
                if body.duration_hours is not None
                else None
            ),
            image_url=body.image_url,
        )
        return quest_to_api(quest)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get(
    "/{quest_id}",
    response_model=Quest,
    response_model_exclude_none=True,
)
async def get_quest(quest_id: str) -> Quest:
    """Fetch a quest by its identifier."""
    try:
        usecase = quest_usecases.GetQuest(quests_repo=quests_repo)
        quest = await usecase.execute(quest_id)
        return quest_to_api(quest)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.patch(
    "/{quest_id}",
    response_model=Quest,
    response_model_exclude_none=True,
)
async def patch_quest(quest_id: str, body: QuestUpdate | None = None) -> Quest:
    """Update top-level quest details such as title and timing."""
    payload = body.model_dump(exclude_unset=True) if body else {}

    try:
        usecase = quest_usecases.UpdateQuestDetails(quests_repo=quests_repo)
        quest = await usecase.execute(
            quest_id,
            title=payload.get("title"),
            description=payload.get("description"),
            starting_at=payload.get("starting_at"),
            duration=(
                timedelta(hours=payload["duration_hours"])
                if "duration_hours" in payload and payload["duration_hours"] is not None
                else None
            ),
            image_url=payload.get("image_url"),
        )
        return quest_to_api(quest)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete("/{quest_id}", status_code=204)
async def delete_quest(quest_id: str) -> None:
    """Remove a quest from the catalog."""
    try:
        usecase = quest_usecases.DeleteQuest(quests_repo=quests_repo)
        await usecase.execute(quest_id)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


# --- Signups ---
@router.post(
    "/{quest_id}/signups",
    response_model=Quest,
    response_model_exclude_none=True,
)
async def add_signup(quest_id: str, payload: QuestSignup) -> Quest:
    """Register a player's signup for a quest."""
    try:
        usecase = quest_usecases.AddPlayerSignup(
            quests_repo=quests_repo,
            users_repo=users_repo,
            characters_repo=chars_repo,
        )
        quest = await usecase.execute(
            quest_id=quest_id,
            user_id=payload.user_id,
            character_id=payload.character_id,
        )
        return quest_to_api(quest)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.delete(
    "/{quest_id}/signups/{user_id}",
    response_model=Quest,
    response_model_exclude_none=True,
)
async def remove_signup(quest_id: str, user_id: str) -> Quest:
    """Remove a player's signup from a quest."""
    try:
        usecase = quest_usecases.RemovePlayerSignup(
            quests_repo=quests_repo,
            users_repo=users_repo,
        )
        quest = await usecase.execute(quest_id, user_id)
        return quest_to_api(quest)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{quest_id}/signups/{user_id}:select",
    response_model=Quest,
    response_model_exclude_none=True,
)
async def select_signup(quest_id: str, user_id: str) -> Quest:
    """Mark a user's signup as selected for the quest."""
    try:
        usecase = quest_usecases.SelectPlayerSignup(
            quests_repo=quests_repo,
            users_repo=users_repo,
        )
        quest = await usecase.execute(quest_id, user_id)
        return quest_to_api(quest)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


# --- Lifecycle commands ---
@router.post(
    "/{quest_id}:closeSignups",
    response_model=Quest,
    response_model_exclude_none=True,
)
async def close_signups(quest_id: str) -> Quest:
    """Set quest signups to closed once the roster is final."""
    try:
        usecase = quest_usecases.CloseQuestSignups(quests_repo=quests_repo)
        quest = await usecase.execute(quest_id)
        return quest_to_api(quest)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{quest_id}:setCompleted",
    response_model=Quest,
    response_model_exclude_none=True,
)
async def set_completed(quest_id: str) -> Quest:
    """Flag a quest as completed."""
    try:
        usecase = quest_usecases.MarkQuestCompleted(quests_repo=quests_repo)
        quest = await usecase.execute(quest_id)
        return quest_to_api(quest)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{quest_id}:setCancelled",
    response_model=Quest,
    response_model_exclude_none=True,
)
async def set_cancelled(quest_id: str) -> Quest:
    """Flag a quest as cancelled."""
    try:
        usecase = quest_usecases.MarkQuestCancelled(quests_repo=quests_repo)
        quest = await usecase.execute(quest_id)
        return quest_to_api(quest)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post(
    "/{quest_id}:setAnnounced",
    response_model=Quest,
    response_model_exclude_none=True,
)
async def set_announced(quest_id: str) -> Quest:
    """Mark a quest as announced to players."""
    try:
        usecase = quest_usecases.MarkQuestAnnounced(quests_repo=quests_repo)
        quest = await usecase.execute(quest_id)
        return quest_to_api(quest)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
