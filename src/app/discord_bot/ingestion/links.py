from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import for type checking
    from app.infra.mongo.quest_records_repo import QuestRecordsRepository


@dataclass(frozen=True, slots=True)
class DiscordMessageKey:
    guild_id: str
    channel_id: str
    message_id: str

    @classmethod
    def from_ids(
        cls, guild_id: int | str, channel_id: int | str, message_id: int | str
    ) -> "DiscordMessageKey":
        return cls(str(guild_id), str(channel_id), str(message_id))

    def as_filter(self) -> dict[str, str]:
        return {
            "discord_channel_id": self.channel_id,
            "discord_message_id": self.message_id,
        }


async def resolve_linked_quests(repo: "QuestRecordsRepository") -> int:
    """Populate missing quest_id on linked quest references.

    Returns the number of links resolved.
    """

    resolved = 0
    async for record in repo.iter_unresolved_links():
        for index, link in enumerate(record.linked_quests):
            if link.quest_id is not None:
                continue
            key = DiscordMessageKey(
                guild_id=link.guild_id,
                channel_id=link.channel_id,
                message_id=link.message_id,
            )
            target = await repo.get_by_discord_key(key)
            if not target:
                continue
            await repo.update_linked_quest_id(record.quest_id, index, target.quest_id)
            resolved += 1
    return resolved
