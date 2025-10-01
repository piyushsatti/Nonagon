from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.models.EntityIDModel import UserID
from app.domain.models.quest.QuestModel import Quest
from app.domain.usecase._shared import ensure_user, parse_quest_id
from app.domain.usecase.ports import QuestsRepo, UsersRepo


@dataclass(slots=True)
class CreateQuest:
    quests_repo: QuestsRepo
    users_repo: UsersRepo

    async def execute(
        self,
        *,
        referee_id: UserID | str,
        channel_id: str,
        message_id: str,
        raw: str | None = None,
        title: str | None = None,
        description: str | None = None,
        starting_at: datetime | None = None,
        duration: timedelta | None = None,
        image_url: str | None = None,
    ) -> Quest:
        referee = await ensure_user(self.users_repo, referee_id)
        if not referee.is_referee:
            raise ValueError(f"User {referee.user_id} is not a referee")

        quest_id = parse_quest_id(await self.quests_repo.next_id())

        quest = Quest(
            quest_id=quest_id,
            referee_id=referee.user_id,
            channel_id=channel_id,
            message_id=message_id,
            raw=raw,
            title=title or "",
            description=description,
            starting_at=starting_at,
            duration=duration,
            image_url=image_url,
        )
        quest.validate_quest()
        await self.quests_repo.upsert(quest)
        return quest
