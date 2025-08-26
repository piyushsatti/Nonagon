from __future__ import annotations
from dataclasses import asdict
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_quests_repo
from app.domain.models.quest.QuestModel import Quest
from app.api.schemas import QuestSchema

from app.domain.models.EntityIDModel import QuestID
from app.infra.id_counter import next_id

router = APIRouter(prefix="/quest")

@router.get("/ping")
async def ping():
  return {"ok": True}

@router.get("/{quest_id}", response_model=QuestSchema)
async def get_quest(
  quest_id: str,
  quests_repo = Depends(get_quests_repo),
):
  try:
    return await quests_repo.get(quest_id)
  except Exception:
    raise HTTPException(status_code=404, detail="Quest not found.")

@router.post("", response_model=QuestSchema, status_code=201)
async def upsert_quest(
  payload: QuestSchema,
  quests_repo = Depends(get_quests_repo),
):
  _id = await next_id(QuestID)
  payload.user_id = str(_id)
  quest = Quest(**payload.model_dump())
  await quests_repo.upsert(quest)
  return await quests_repo.get(quest.quest_id)

@router.patch("/{quest_id}", response_model=QuestSchema)
async def patch_quest(
  quest_id: str,
  patch: Dict[str, Any],
  quests_repo = Depends(get_quests_repo),
):
  try:
    current: Quest = await quests_repo.get(quest_id)
  except Exception:
    raise HTTPException(status_code=404, detail="Quest not found.")

  merged = {**asdict(current), **patch, "quest_id": quest_id}
  await quests_repo.upsert(Quest(**merged))
  return await quests_repo.get(quest_id)
