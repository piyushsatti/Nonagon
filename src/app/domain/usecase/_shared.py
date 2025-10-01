from __future__ import annotations

from typing import Iterable, Sequence, TypeVar

from app.domain.models.character.CharacterModel import Character
from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID
from app.domain.models.quest.QuestModel import Quest
from app.domain.models.summary.SummaryModel import QuestSummary
from app.domain.models.user.UserModel import User
from app.domain.usecase.ports import (
    CharactersRepo,
    QuestsRepo,
    SummariesRepo,
    UsersRepo,
)


def parse_user_id(raw: UserID | str) -> UserID:
    """Return a strongly-typed ``UserID`` from raw inputs."""

    if isinstance(raw, UserID):
        return raw
    return UserID.parse(str(raw))


def parse_character_id(raw: CharacterID | str) -> CharacterID:
    if isinstance(raw, CharacterID):
        return raw
    return CharacterID.parse(str(raw))


def parse_quest_id(raw: QuestID | str) -> QuestID:
    if isinstance(raw, QuestID):
        return raw
    return QuestID.parse(str(raw))


def parse_summary_id(raw: SummaryID | str) -> SummaryID:
    if isinstance(raw, SummaryID):
        return raw
    return SummaryID.parse(str(raw))


async def ensure_user(users_repo: UsersRepo, user_id: UserID | str) -> User:
    user = await users_repo.get(str(parse_user_id(user_id)))
    if user is None:
        raise ValueError(f"User ID does not exist: {user_id}")
    return user


async def ensure_character(
    characters_repo: CharactersRepo, character_id: CharacterID | str
) -> Character:
    char = await characters_repo.get(str(parse_character_id(character_id)))
    if char is None:
        raise ValueError(f"Character ID does not exist: {character_id}")
    return char


async def ensure_quest(quests_repo: QuestsRepo, quest_id: QuestID | str) -> Quest:
    quest = await quests_repo.get(str(parse_quest_id(quest_id)))
    if quest is None:
        raise ValueError(f"Quest ID does not exist: {quest_id}")
    return quest


async def ensure_summary(
    summaries_repo: SummariesRepo, summary_id: SummaryID | str
) -> QuestSummary:
    summary = await summaries_repo.get(str(parse_summary_id(summary_id)))
    if summary is None:
        raise ValueError(f"Summary ID does not exist: {summary_id}")
    return summary


T = TypeVar("T")


def ensure_distinct(items: Iterable[T]) -> list[T]:
    """Deduplicate while preserving order."""

    seen: set[T] = set()
    ordered: list[T] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def coerce_sequence(value: Sequence[T] | None) -> list[T]:
    if value is None:
        return []
    return list(value)
