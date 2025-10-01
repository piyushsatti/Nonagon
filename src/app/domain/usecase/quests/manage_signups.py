from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.EntityIDModel import CharacterID, QuestID, UserID
from app.domain.models.quest.QuestModel import Quest
from app.domain.usecase._shared import (
    ensure_character,
    ensure_quest,
    ensure_user,
    parse_character_id,
)
from app.domain.usecase.ports import CharactersRepo, QuestsRepo, UsersRepo


@dataclass(slots=True)
class AddPlayerSignup:
    quests_repo: QuestsRepo
    users_repo: UsersRepo
    characters_repo: CharactersRepo

    async def execute(
        self,
        quest_id: QuestID | str,
        user_id: UserID | str,
        character_id: CharacterID | str,
    ) -> Quest:
        quest = await ensure_quest(self.quests_repo, quest_id)
        user = await ensure_user(self.users_repo, user_id)
        character = await ensure_character(self.characters_repo, character_id)

        if not user.is_player:
            raise ValueError(f"User {user.user_id} is not a player")

        char_id = parse_character_id(character_id)
        if character.owner_id != user.user_id:
            raise ValueError(
                f"Character {character.character_id} does not belong to user {user.user_id}"
            )

        if not quest.is_signup_open:
            raise ValueError(f"Signups are closed for quest {quest.quest_id}")

        quest.add_signup(user.user_id, char_id)
        await self.quests_repo.upsert(quest)
        return quest


@dataclass(slots=True)
class RemovePlayerSignup:
    quests_repo: QuestsRepo
    users_repo: UsersRepo

    async def execute(self, quest_id: QuestID | str, user_id: UserID | str) -> Quest:
        quest = await ensure_quest(self.quests_repo, quest_id)
        user = await ensure_user(self.users_repo, user_id)

        quest.remove_signup(user.user_id)
        await self.quests_repo.upsert(quest)
        return quest


@dataclass(slots=True)
class SelectPlayerSignup:
    quests_repo: QuestsRepo
    users_repo: UsersRepo

    async def execute(self, quest_id: QuestID | str, user_id: UserID | str) -> Quest:
        quest = await ensure_quest(self.quests_repo, quest_id)
        user = await ensure_user(self.users_repo, user_id)

        if not user.is_player:
            raise ValueError(f"User {user.user_id} is not a player")

        quest.select_signup(user.user_id)
        await self.quests_repo.upsert(quest)
        return quest


@dataclass(slots=True)
class CloseQuestSignups:
    quests_repo: QuestsRepo

    async def execute(self, quest_id: QuestID | str) -> Quest:
        quest = await ensure_quest(self.quests_repo, quest_id)
        quest.close_signups()
        await self.quests_repo.upsert(quest)
        return quest
