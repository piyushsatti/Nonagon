from __future__ import annotations
from datetime import datetime, timezone
from typing import Tuple

# Domain Imports
from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID
from app.domain.models.UserModel import User
from app.domain.models.CharacterModel import Character

# Adding ports
from app.domain.usecase.ports import UsersRepo, CharactersRepo, QuestsRepo, SummariesRepo

users_repo: UsersRepo = UsersRepo()

# ------- CRUD Operations -------
def create_user(discord_id: str = None, dm_channel_id: str = None) -> User:
  """
  Creates a new user from parameters.
  Raises ValueError if user with same ID already exists.
  """

  user = User(
    user_id=users_repo.next_id(),
    discord_id=discord_id,
    dm_channel_id=dm_channel_id,
    joined_at=datetime.now(timezone.utc),
    last_active_at=datetime.now(timezone.utc),
  )