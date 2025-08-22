# src/app/api/routers/quests.py
from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_quests_repo
from app.api.security import get_current_user, require_admin
from app.api.schemas import QuestCreate, QuestUpdate, QuestOutAdmin, QuestOutUser
from app.domain.models.QuestModel import Quest
from app.domain.models.UserModel import User, Role
from app.domain.usecases.ports import ForbiddenError, NotFoundError

router = APIRouter(prefix="/quests", tags=["quests"])


def _to_admin_view(q: Quest) -> QuestOutAdmin:
    return QuestOutAdmin(
        quest_id=q.quest_id, name=q.name, dm_id=q.dm_id,
        description=q.description, scheduled_at=q.scheduled_at,
        max_players=q.max_players, min_players=q.min_players,
        category=q.category, tags=q.tags, region=q.region,
        level_min=q.level_min, level_max=q.level_max,
        status=q.status.value if hasattr(q.status, "value") else str(q.status),
        roster=q.roster, waitlist=q.waitlist, signups=q.signups,
        summary_ids=q.summary_ids, guild_id=q.guild_id, channel_id=q.channel_id,
        signup_message_id=q.signup_message_id, thread_id=q.thread_id,
    )

def _to_user_view(q: Quest) -> QuestOutUser:
    return QuestOutUser(
        quest_id=q.quest_id, name=q.name, dm_id=q.dm_id,
        description=q.description, scheduled_at=q.scheduled_at,
        max_players=q.max_players, min_players=q.min_players,
        category=q.category, tags=q.tags, region=q.region,
        level_min=q.level_min, level_max=q.level_max,
        status=q.status.value if hasattr(q.status, "value") else str(q.status),
    )


# ---- Create (admin only) ----
@router.post("", response_model=QuestOutAdmin, status_code=status.HTTP_201_CREATED)
async def create_quest(payload: QuestCreate, quests_repo = Depends(get_quests_repo), _: User = Depends(require_admin)):
    # Minimal direct create using repo.next_id()
    qid = await quests_repo.next_id()
    q = Quest(
        quest_id=qid, name=payload.name, dm_id=payload.dm_id,
        description=payload.description, scheduled_at=payload.scheduled_at,
        max_players=payload.max_players, min_players=payload.min_players,
        category=payload.category, tags=payload.tags or [],
        region=payload.region, level_min=payload.level_min, level_max=payload.level_max,
    )
    await quests_repo.upsert(q)
    return _to_admin_view(q)


# ---- Read one (role-aware output) ----
@router.get("/{quest_id}", response_model=Union[QuestOutAdmin, QuestOutUser])
async def get_quest(quest_id: str, quests_repo = Depends(get_quests_repo), user: User = Depends(get_current_user)):
    try:
        q = await quests_repo.get(quest_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Quest not found")
    if Role.ADMIN in user.roles:
        return _to_admin_view(q)
    return _to_user_view(q)


# ---- List (role-aware) ----
@router.get("", response_model=List[QuestOutUser])
async def list_quests(quests_repo = Depends(get_quests_repo), user: User = Depends(get_current_user)):
    # Keep it simple: list all quests and map by role
    # Add filters/pagination later
    items = await quests_repo.list_for_dm(dm_id=user.user_id) if Role.REFEREE in user.roles else []
    # In a real list() you would query all; here we demonstrate shape with subset.
    # To list all for everyone, add a repo method list_all().
    return [_to_user_view(q) for q in items]


# ---- Update (admin only) ----
@router.patch("/{quest_id}", response_model=QuestOutAdmin)
async def update_quest(quest_id: str, payload: QuestUpdate, quests_repo = Depends(get_quests_repo), _: User = Depends(require_admin)):
    try:
        q = await quests_repo.get(quest_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Quest not found")

    # apply partial updates
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(q, k, v)

    await quests_repo.upsert(q)
    return _to_admin_view(q)


# ---- Delete (admin only) ----
@router.delete("/{quest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quest(quest_id: str, quests_repo = Depends(get_quests_repo), _: User = Depends(require_admin)):
    try:
        _ = await quests_repo.get(quest_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Quest not found")
    # For simplicity, a "soft delete": set category to 'deleted' or add a flag.
    # If you want hard delete, implement repo.delete(quest_id).
    # Here we'll simulate hard delete with a raw call:
    quests_repo.col.delete_one({"quest_id": quest_id})
    return None
