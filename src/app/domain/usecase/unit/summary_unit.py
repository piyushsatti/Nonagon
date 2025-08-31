from __future__ import annotations
from datetime import datetime, timezone
from typing import Tuple, Optional

# Domain Imports
from app.domain.models.EntityIDModel import UserID, CharacterID, QuestID, SummaryID
from app.domain.models.SummaryModel import QuestSummary, SummaryKind

# Adding ports
from app.domain.usecase.ports import UsersRepo, CharactersRepo, QuestsRepo, SummariesRepo

# ------- CRUD -------

def create_summary(
  summaries_repo: SummariesRepo,
  users_repo: UsersRepo,
  char_repo: CharactersRepo,
  quest_repo: QuestsRepo,
  kind: SummaryKind,
  author_id: UserID,
  character_id: CharacterID,
  quest_id: QuestID,
  raw: str,
  title: str,
  description: str,
  created_on: datetime = datetime.now(timezone.utc),
  players: Tuple[UserID] = tuple(),
  characters: Tuple[CharacterID] = tuple(),
  linked_quests: Tuple[QuestID] = tuple(),
  linked_summaries: Tuple[SummaryID] = tuple(),
) -> QuestSummary:
  """
  Creates a new summary from parameters.
  Raises ValueError if user, character, or quest does not exist.
  """

  if not users_repo.exists(author_id):
    raise ValueError(f"Author ID does not exist: {author_id}")

  if not char_repo.exists(character_id):
    raise ValueError(f"Character ID does not exist: {character_id}")

  if not quest_repo.exists(quest_id):
    raise ValueError(f"Quest ID does not exist: {quest_id}")

  summary = QuestSummary(
    summary_id=summaries_repo.next_id(),
    kind=kind,
    author_id=author_id,
    character_id=character_id,
    quest_id=quest_id,
    raw=raw,
    title=title,
    description=description,
    created_on=created_on,
    players=players,
    characters=characters,
    linked_quests=linked_quests,
    linked_summaries=linked_summaries,
  )

  summary.validate_summary()

  summaries_repo.upsert(summary)

  return summary

def get_summary(summaries_repo: SummariesRepo, summary_id: SummaryID) -> QuestSummary:
  """
  Fetches a summary by its ID.
  Raises ValueError if summary does not exist.
  """

  if not summaries_repo.exists(summary_id):
    raise ValueError(f"Summary with ID {summary_id} does not exist.")
  
  return summaries_repo.get(summary_id)

def update_summary(summaries_repo: SummariesRepo, summary: QuestSummary) -> QuestSummary:
  """
  Updates an existing summary.
  Raises ValueError if summary does not exist.
  """
  
  if not summaries_repo.exists(summary.summary_id):
    raise ValueError(f"Summary with ID {summary.summary_id} does not exist.")
  
  summaries_repo.upsert(summary)
  
  return summary

def delete_summary(summaries_repo: SummariesRepo, summary_id: SummaryID) -> None:
  """
  Deletes a summary by its ID.
  Raises ValueError if summary does not exist.
  """
  
  if not summaries_repo.exists(summary_id):
    raise ValueError(f"Summary with ID {summary_id} does not exist.")
  
  summaries_repo.delete(summary_id)
  
  return None

def update_last_edited(summaries_repo: SummariesRepo, summary_id: SummaryID, edited_at: Optional[datetime] = None) -> QuestSummary:
  """
  Updates the last_edited_at timestamp for a summary.
  Raises ValueError if summary does not exist.
  """
  
  if not summaries_repo.exists(summary_id):
    raise ValueError(f"Summary with ID {summary_id} does not exist.")
  
  summary = get_summary(summaries_repo, summary_id)
  
  summary.last_edited_at = edited_at or datetime.now(timezone.utc)
  
  summaries_repo.upsert(summary)
  
  return summary

# ------- Link Operations -------
def add_player_to_summary(
  users_repo: UsersRepo,
  summaries_repo: SummariesRepo,
  summary_id: SummaryID,
  player_id: UserID
) -> QuestSummary:
  """
  If a player exists,
  Adds a player to the summary's players list.
  Raises ValueError if summary does not exist or player already added.
  """
  
  if not users_repo.exists(player_id):
    raise ValueError(f"User with ID {player_id} does not exist.")

  if not summaries_repo.exists(summary_id):
    raise ValueError(f"Summary with ID {summary_id} does not exist.")

  summary = get_summary(summaries_repo, summary_id)

  if player_id in summary.players:
    raise ValueError(f"Player {player_id} already in summary {summary_id}")

  summary.players.append(player_id)

  summaries_repo.upsert(summary)

  return summary

def remove_player_from_summary(
  users_repo: UsersRepo,
  summaries_repo: SummariesRepo,
  summary_id: SummaryID,
  player_id: UserID
) -> QuestSummary:
  """
  If a player exists,
  Removes a player from the summary's players list.
  Raises ValueError if summary does not exist or player not in list.
  """
  
  if not users_repo.exists(player_id):
    raise ValueError(f"User with ID {player_id} does not exist.")

  if not summaries_repo.exists(summary_id):
    raise ValueError(f"Summary with ID {summary_id} does not exist.")

  summary = get_summary(summaries_repo, summary_id)

  if player_id not in summary.players:
    raise ValueError(f"Player {player_id} not in summary {summary_id}")

  summary.players.remove(player_id)

  summaries_repo.upsert(summary)

  return summary 

def add_character_to_summary(
  char_repo: CharactersRepo,
  summaries_repo: SummariesRepo,
  summary_id: SummaryID,
  character_id: CharacterID
) -> QuestSummary:
  """
  If a character exists,
  Adds a character to the summary's characters list.
  Raises ValueError if summary does not exist or character already added.
  """
  
  if not char_repo.exists(character_id):
    raise ValueError(f"Character with ID {character_id} does not exist.")

  if not summaries_repo.exists(summary_id):
    raise ValueError(f"Summary with ID {summary_id} does not exist.")

  summary = get_summary(summaries_repo, summary_id)

  if character_id in summary.characters:
    raise ValueError(f"Character {character_id} already in summary {summary_id}")

  summary.characters.append(character_id)

  summaries_repo.upsert(summary)

  return summary

def remove_character_from_summary(
  char_repo: CharactersRepo,
  summaries_repo: SummariesRepo,
  summary_id: SummaryID,
  character_id: CharacterID
) -> QuestSummary:
  """
  If a character exists,
  Removes a character from the summary's characters list.
  Raises ValueError if summary does not exist or character not in list.
  """
  
  if not char_repo.exists(character_id):
    raise ValueError(f"Character with ID {character_id} does not exist.")

  if not summaries_repo.exists(summary_id):
    raise ValueError(f"Summary with ID {summary_id} does not exist.")

  summary = get_summary(summaries_repo, summary_id)

  if character_id not in summary.characters:
    raise ValueError(f"Character {character_id} not in summary {summary_id}")

  summary.characters.remove(character_id)

  summaries_repo.upsert(summary)

  return summary 

# ------- Query Operations -------

def list_summaries(summaries_repo: SummariesRepo, limit: int = 100, offset: int = 0) -> Tuple[QuestSummary]:
  """
  Lists summaries with pagination.
  """
  
  return summaries_repo.list(limit=limit, offset=offset)

def list_summaries_by_author(summaries_repo: SummariesRepo, author_id: UserID, limit: int = 100, offset: int = 0) -> Tuple[QuestSummary]:
  """
  Lists summaries by a specific author with pagination.
  """
  
  return summaries_repo.list_by_author(author_id=author_id, limit=limit, offset=offset)

def list_summaries_by_character(summaries_repo: SummariesRepo, character_id: CharacterID, limit: int = 100, offset: int = 0) -> Tuple[QuestSummary]:
  """
  Lists summaries involving a specific character with pagination.
  """
  
  return summaries_repo.list_by_character(character_id=character_id, limit=limit, offset=offset)

def list_summaries_by_player(summaries_repo: SummariesRepo, player_id: UserID, limit: int = 100, offset: int = 0) -> Tuple[QuestSummary]:
  """
  Lists summaries involving a specific player with pagination.
  """
  
  return summaries_repo.list_by_player(player_id=player_id, limit=limit, offset=offset)