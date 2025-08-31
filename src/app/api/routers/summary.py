from __future__ import annotations
from dataclasses import asdict
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_summaries_repo
from app.domain.models.SummaryModel import QuestSummary
from app.api.schemas import SummarySchema

from app.domain.models.EntityIDModel import SummaryID
from app.infra.id_counter import next_id

router = APIRouter(prefix="/summary")

@router.get("/ping")
async def ping():
  return {"ok": True}

@router.get("/{summary_id}", response_model=SummarySchema)
async def get_summary(
  summary_id: str,
  summaries_repo = Depends(get_summaries_repo),
):
  try:
    return await summaries_repo.get(summary_id)
  except Exception:
    raise HTTPException(status_code=404, detail="Summary not found.")

@router.post("", response_model=SummarySchema, status_code=201)
async def create_or_upsert_summary(
  payload: SummarySchema,
  summaries_repo = Depends(get_summaries_repo),
):
  data = payload.model_dump()
  new_id = await next_id(SummaryID)
  data["summary_id"] = str(new_id)
  summary = QuestSummary(**data)
  await summaries_repo.upsert(summary)
  return await summaries_repo.get(summary.summary_id)

@router.patch("/{summary_id}", response_model=SummarySchema)
async def patch_summary(
  summary_id: str,
  patch: Dict[str, Any],
  summaries_repo = Depends(get_summaries_repo),
):
  try:
    current: QuestSummary = await summaries_repo.get(summary_id)
  except Exception:
    raise HTTPException(status_code=404, detail="Summary not found.")

  merged = {**asdict(current), **patch, "summary_id": summary_id}
  await summaries_repo.upsert(QuestSummary(**merged))
  return await summaries_repo.get(summary_id)
