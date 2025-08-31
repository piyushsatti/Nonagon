from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.domain.models.QuestModel import Quest
from app.domain.models.SummaryModel import QuestSummary
from app.domain.models.CharacterModel import Character
from app.domain.models.UserModel import User


class UserSchema(BaseModel, User):
  model_config = ConfigDict(from_attributes=True)


class QuestSchema(BaseModel, Quest):
  model_config = ConfigDict(from_attributes=True)


class SummarySchema(BaseModel, QuestSummary):
  model_config = ConfigDict(from_attributes=True)


class CharacterSchema(BaseModel, Character):
  model_config = ConfigDict(from_attributes=True)

