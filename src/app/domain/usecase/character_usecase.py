from __future__ import annotations
from datetime import datetime, timezone
from typing import Tuple

# Domain Imports
from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID
from app.domain.models.UserModel import User
from app.domain.models.CharacterModel import Character

# Adding ports
from app.domain.usecase.ports import UsersRepo, CharactersRepo, QuestsRepo, SummariesRepo

# ------- CRUD Operations -------

def create_character(
  char_repo: CharactersRepo,
  users_repo: UsersRepo,
  owner_id: UserID,
  name: str,
  ddb_link: str,
  character_thread_link: str,
  token_link: str,
  art_link: str,
  description: str = None,
  notes: str = None,
  tags: Tuple[str] = (),
) -> Character:
  """
  Creates a new character from parameters.
  """

  if not users_repo.exists(owner_id):
    raise ValueError(f"Owner ID does not exist: {owner_id}")

  char = Character(
    owner_id=owner_id,
    character_id=char_repo.next_id(),
    name=name,
    ddb_link=ddb_link,
    character_thread_link=character_thread_link,
    token_link=token_link,
    art_link=art_link,
    description=description,
    notes=notes,
    tags=tags,
    created_at=datetime.now(timezone.utc),
  )

  char.validate_character()

  char_repo.upsert(char)

  return char

def get_character(char_repo: CharactersRepo, character_id: CharacterID) -> Character:
  """
  Fetches a character by its ID.
  Raises ValueError if character does not exist.
  """
  
  char = char_repo.get(character_id)
  
  if not char:
    raise ValueError(f"Character with ID {character_id} does not exist.")
  
  return char

def update_character(char_repo: CharactersRepo, char: Character) -> Character:
  """
  Updates an existing character.
  Raises ValueError if character does not exist.
  """
  
  if not char_repo.exists(char.character_id):
    raise ValueError(f"Character with ID {char.character_id} does not exist.")
  
  char_repo.upsert(char)
  
  return char

def delete_character(char_repo: CharactersRepo, character_id: CharacterID) -> None:
  """
  Deletes a character by its ID.
  Raises ValueError if character does not exist.
  """
  
  if not char_repo.exists(character_id):
    raise ValueError(f"Character with ID {character_id} does not exist.")
  
  # Assuming character_repo has a delete method
  char_repo.delete(character_id)
  
  return None

# ------- Telemetry Operations -------

def increment_quests_played(char_repo: CharactersRepo, character_id: CharacterID) -> Character:
  """
  Increments the quests_played count for a character.
  Raises ValueError if character does not exist.
  """
  
  char = get_character(character_id)
  
  char.increment_quests_played()
  
  char_repo.upsert(char)
  
  return char
  
def increment_summaries_written(char_repo: CharactersRepo, character_id: CharacterID) -> Character:
  """
  Increments the summaries_written count for a character.
  Raises ValueError if character does not exist.
  """
  
  char = get_character(character_id)
  
  char.increment_summaries_written()
  
  char_repo.upsert(char)
  
  return char

def update_last_played_at(char_repo: CharactersRepo, character_id: CharacterID, played_at: datetime = None) -> Character:
  """
  Updates the last_played_at timestamp for a character.
  Raises ValueError if character does not exist or if played_at is before created_at.
  """
  
  char = get_character(character_id)
  
  if played_at is None:
    played_at = datetime.now(timezone.utc)
  
  char.update_last_played(played_at)
  
  char_repo.upsert(char)
  
  return char

# ------- Link Operations -------
def add_played_with(char_repo: CharactersRepo, character_id: CharacterID, other_char_id: CharacterID) -> Character:
  """
  Adds another character to the played_with list.
  Raises ValueError if character does not exist.
  """
  
  char = get_character(character_id)
  
  char.add_played_with(other_char_id)
  
  char_repo.upsert(char)
  
  return char

def remove_played_with(char_repo: CharactersRepo, character_id: CharacterID, other_char_id: CharacterID) -> Character:
  """
  Removes another character from the played_with list.
  Raises ValueError if character does not exist.
  """
  
  char = get_character(character_id)
  
  char.remove_played_with(other_char_id)
  
  char_repo.upsert(char)
  
  return char

def add_played_in(char_repo: CharactersRepo, character_id: CharacterID, quest_id: QuestID) -> Character:
  """
  Adds a quest to the played_in list.
  Raises ValueError if character does not exist.
  """
  
  char = get_character(character_id)
  
  char.add_played_in(quest_id)
  
  char_repo.upsert(char)
  
  return char

def remove_played_in(char_repo: CharactersRepo, character_id: CharacterID, quest_id: QuestID) -> Character:
  """
  Removes a quest from the played_in list.
  Raises ValueError if character does not exist.
  """
  
  char = get_character(character_id)
  
  char.remove_played_in(quest_id)
  
  char_repo.upsert(char)
  
  return char

def add_mentioned_in(char_repo: CharactersRepo, character_id: CharacterID, summary_id: SummaryID) -> Character:
  """
  Adds a summary to the mentioned_in list.
  Raises ValueError if character does not exist.
  """
  
  char = get_character(character_id)
  
  char.add_mentioned_in(summary_id)
  
  char_repo.upsert(char)
  
  return char

def remove_mentioned_in(char_repo: CharactersRepo, character_id: CharacterID, summary_id: SummaryID) -> Character:
  """
  Removes a summary from the mentioned_in list.
  Raises ValueError if character does not exist.
  """
  
  char = get_character(character_id)
  
  char.remove_mentioned_in(summary_id)
  
  char_repo.upsert(char)
  
  return char