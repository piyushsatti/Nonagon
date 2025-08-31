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
  author_id: UserID,
  character_id: CharacterID,
  quest_id: QuestID,
  kind: SummaryKind,
  raw: str,
  title: str,
  description: str,
  players: Tuple[UserID] = (),
  characters: Tuple[CharacterID] = (),
  linked_quests: Tuple[QuestID] = (),
  linked_summaries: Tuple[SummaryID] = (),
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
    created_on=datetime.now(timezone.utc),
    players=players,
    characters=characters,
    linked_quests=linked_quests,
    linked_summaries=linked_summaries,
  )
  
  summary.validate_summary()
  
  summaries_repo.upsert(summary)
  
  return summary