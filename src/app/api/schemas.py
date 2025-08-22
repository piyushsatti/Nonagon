# src/app/api/schemas.py
from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

# ---- Auth ----
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginIn(BaseModel):
    user_id: str
    password: str = Field(..., description="Demo only; replace with real auth later")

# ---- Quests ----
class QuestCreate(BaseModel):
    name: str
    dm_id: str
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    max_players: int = 5
    min_players: int = 3
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    region: Optional[str] = None
    level_min: Optional[int] = None
    level_max: Optional[int] = None

class QuestUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    max_players: Optional[int] = None
    min_players: Optional[int] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    region: Optional[str] = None
    level_min: Optional[int] = None
    level_max: Optional[int] = None

# “Admin view” (full)
class QuestOutAdmin(BaseModel):
    quest_id: str
    name: str
    dm_id: str
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    max_players: int
    min_players: int
    category: Optional[str] = None
    tags: List[str] = []
    region: Optional[str] = None
    level_min: Optional[int] = None
    level_max: Optional[int] = None
    status: str
    roster: list = []
    waitlist: list = []
    signups: list = []
    summary_ids: List[str] = []
    guild_id: Optional[int] = None
    channel_id: Optional[int] = None
    signup_message_id: Optional[int] = None
    thread_id: Optional[int] = None

# “User view” (subset)
class QuestOutUser(BaseModel):
    quest_id: str
    name: str
    dm_id: str
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    max_players: int
    min_players: int
    category: Optional[str] = None
    tags: List[str] = []
    region: Optional[str] = None
    level_min: Optional[int] = None
    level_max: Optional[int] = None
    status: str
