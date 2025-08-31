from __future__ import annotations
from dataclasses import asdict
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.domain.models.UserModel import User
from app.domain.models.EntityIDModel import UserID
from app.infra.id_counter import next_id
from app.api.deps import get_users_repo
from app.api.schemas import UserSchema

router = APIRouter(prefix="/user", tags=["user"])

@router.get("/ping")
async def ping():
  return {"ok": True}

@router.get("/{user_id}", response_model=UserSchema)
async def get_user(
  user_id: str,
  users_repo = Depends(get_users_repo),
):
  try:
    return await users_repo.get(user_id)
  except Exception:
    raise HTTPException(status_code=404, detail="User not found")

@router.post("", response_model=UserSchema, status_code=201)
async def create_or_upsert_user(
  payload: UserSchema,
  users_repo = Depends(get_users_repo),
):
  _id = await next_id(UserID)
  payload.user_id = str(_id)
  user = User(**payload.model_dump())
  await users_repo.upsert(user)
  return await users_repo.get(user.user_id)

@router.patch("/{user_id}", response_model=UserSchema)
async def patch_user(
  user_id: str,
  patch: Dict[str, Any],
  users_repo = Depends(get_users_repo),
):
  try:
    current: User = await users_repo.get(user_id)
  except Exception:
    raise HTTPException(status_code=404, detail="User not found")

  merged = {**asdict(current), **patch, "user_id": user_id}
  await users_repo.upsert(User(**merged))
  return await users_repo.get(user_id)
