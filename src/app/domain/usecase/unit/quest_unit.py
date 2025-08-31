from __future__ import annotations
from datetime import datetime, timezone
from typing import Tuple

from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID
from app.domain.models.QuestModel import Quest, QuestStatus, PlayerSignUp, PlayerStatus
from app.domain.models.UserModel import User
from app.domain.models.CharacterModel import Character

from app.domain.usecase.ports import QuestsRepo, UsersRepo, CharactersRepo, SummariesRepo

# ------- CRUD -------

def create_quest(
  quest_repo: QuestsRepo,
  users_repo: UsersRepo,
  referee_id: UserID,
  channel_id: str,
  message_id: str,
  raw: str,
  title: str = None,
  description: str = None,
  starting_at: datetime = None,
  duration: datetime = None,
  image_url: str = None
) -> Quest:
  """Create a new Quest object."""

  if not users_repo.exists(referee_id):
    raise ValueError(f"Referee ID does not exist: {referee_id}")
  else:
    referee = users_repo.get(referee_id)
    if not referee.is_referee:
      raise ValueError(f"User is not a referee: {referee_id}")
  
  quest = Quest(
    quest_id=quest_repo.next_id(),
    referee_id=referee_id,
    channel_id=channel_id,
    message_id=message_id,
    raw=raw,
    title=title,
    description=description,
    starting_at=starting_at,
    duration=duration,
    image_url=image_url,
  )

  quest_repo.upsert(quest)

  return quest
  
def get_quest(quest_repo: QuestsRepo, quest_id: QuestID) -> Quest:
  """
  Fetches a quest by its ID.
  Raises ValueError if quest does not exist.
  """

  if not quest_repo.exists(quest_id):
    raise ValueError(f"Quest ID does not exist: {quest_id}")

  return quest_repo.get(quest_id)

def update_quest(
  quest_repo: QuestsRepo,
  quest_id: QuestID,
  title: str = None,
  description: str = None,
  starting_at: datetime = None,
  duration: datetime = None,
  image_url: str = None,
) -> Quest:
  """
  Updates an existing quest with new parameters.
  Raises ValueError if quest does not exist.
  """

  if not quest_repo.exists(quest_id):
    raise ValueError(f"Quest ID does not exist: {quest_id}")

  quest = quest_repo.get(quest_id)

  if title is not None:
    quest.title = title
  
  if description is not None:
    quest.description = description
  
  if starting_at is not None:
    quest.starting_at = starting_at
  
  if duration is not None:
    quest.duration = duration
  
  if image_url is not None:
    quest.image_url = image_url

  quest.validate_quest()

  quest_repo.upsert(quest)

  return quest

def delete_quest(quest_repo: QuestsRepo, quest_id: QuestID) -> bool:
  """
  Deletes a quest by its ID.
  Raises ValueError if quest does not exist.
  """

  if not quest_repo.exists(quest_id):
    raise ValueError(f"Quest ID does not exist: {quest_id}")

  return quest_repo.delete(quest_id)

# ------- Signups -------

def add_player_signup(
  quest_repo: QuestsRepo,
  users_repo: UsersRepo,
  characters_repo: CharactersRepo,
  quest_id: QuestID,
  user_id: UserID,
  character_id: CharacterID
) -> Quest:
  """
  Adds a player signup to a quest.
  Raises ValueError if quest, user, or character does not exist.
  """

  if not quest_repo.exists(quest_id):
    raise ValueError(f"Quest ID does not exist: {quest_id}")
  
  if not users_repo.exists(user_id):
    raise ValueError(f"User ID does not exist: {user_id}")
  
  if not characters_repo.exists(character_id):
    raise ValueError(f"Character ID does not exist: {character_id}")

  quest: Quest = quest_repo.get(quest_id)
  user: User = users_repo.get(user_id)

  if not user.is_player:
    raise ValueError(f"User {user_id} is not a player")

  if not user.is_character_owner(character_id):
    raise ValueError(f"Character {character_id} does not belong to user {user_id}")

  if not quest.is_signup_open:
    raise ValueError(f"Signups are closed for quest {quest_id}")

  quest.add_signup(user_id, character_id)

  quest_repo.upsert(quest)

  return quest

def select_player_signup(
  quest_repo: QuestsRepo,
  users_repo: UsersRepo,
  quest_id: QuestID,
  user_id: UserID
) -> Quest:
  """
  Selects a player's signup for a quest.
  Raises ValueError if quest or user does not exist.
  """

  if not quest_repo.exists(quest_id):
    raise ValueError(f"Quest ID does not exist: {quest_id}")
  
  if not users_repo.exists(user_id):
    raise ValueError(f"User ID does not exist: {user_id}")

  quest: Quest = quest_repo.get(quest_id)
  user: User = users_repo.get(user_id)

  if not user.is_player:
    raise ValueError(f"User {user_id} is not a player")

  quest.select_signup(user_id)

  quest_repo.upsert(quest)

  return quest

def remove_player_signup(
  quest_repo: QuestsRepo,
  users_repo: UsersRepo,
  quest_id: QuestID,
  user_id: UserID
) -> Quest:
  """
  Removes a player signup from a quest.
  Raises ValueError if quest or user does not exist.
  """

  if not quest_repo.exists(quest_id):
    raise ValueError(f"Quest ID does not exist: {quest_id}")
  
  if not users_repo.exists(user_id):
    raise ValueError(f"User ID does not exist: {user_id}")

  quest: Quest = quest_repo.get(quest_id)
  user: User = users_repo.get(user_id)

  if not user.is_player:
    raise ValueError(f"User {user_id} is not a player")

  quest.remove_signup(user_id)

  quest_repo.upsert(quest)

  return quest

def close_quest_signups(quest_repo: QuestsRepo, quest_id: QuestID) -> Quest:
  """
  Closes signups for a quest.
  Raises ValueError if quest does not exist.
  """
  
  if not quest_repo.exists(quest_id):
    raise ValueError(f"Quest ID does not exist: {quest_id}")
  
  quest: Quest = quest_repo.get(quest_id)

  quest.close_signups()

  quest_repo.upsert(quest)

  return quest

# ------- Status Changes -------

def set_quest_completed(quest_repo: QuestsRepo, quest_id: QuestID) -> Quest:
  """
  Sets a quest's status to COMPLETED.
  Raises ValueError if quest does not exist or cannot be completed.
  """

  if not quest_repo.exists(quest_id):
    raise ValueError(f"Quest ID does not exist: {quest_id}")

  quest: Quest = quest_repo.get(quest_id)

  quest.set_completed()

  quest_repo.upsert(quest)

  return quest

def set_quest_cancelled(quest_repo: QuestsRepo, quest_id: QuestID) -> Quest:
  """
  Sets a quest's status to CANCELLED.
  Raises ValueError if quest does not exist or cannot be cancelled.
  """

  if not quest_repo.exists(quest_id):
    raise ValueError(f"Quest ID does not exist: {quest_id}")

  quest: Quest = quest_repo.get(quest_id)

  quest.set_cancelled()

  quest_repo.upsert(quest)

  return quest

def set_quest_announced(quest_repo: QuestsRepo, quest_id: QuestID) -> Quest:
  """
  Sets a quest's status to ANNOUNCED.
  Raises ValueError if quest does not exist or cannot be set to announced.
  """

  if not quest_repo.exists(quest_id):
    raise ValueError(f"Quest ID does not exist: {quest_id}")

  quest: Quest = quest_repo.get(quest_id)

  quest.set_announced()

  quest_repo.upsert(quest)

  return quest

