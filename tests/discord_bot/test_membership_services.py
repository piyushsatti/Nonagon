from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from types import SimpleNamespace
from typing import cast

import discord
import pytest

from app.discord_bot.cogs.character_commands import CharacterCommandsCog
from app.discord_bot.config import DiscordBotConfig
from app.discord_bot.services.character_creation import (
    CharacterCreatePayload,
    CharacterCreationResult,
    CharacterCreationService,
    PlayerRoleRequiredError,
)
from app.discord_bot.services.role_management import (
    PlayerRoleStatus,
    RefereeRoleStatus,
    RoleManagementService,
)
from app.discord_bot.services.user_provisioning import (
    SyncStats,
    UserProvisioningService,
)
from app.domain.models.character.CharacterModel import Character
from app.domain.models.user.UserModel import Player, Role, User
from app.domain.usecase._shared import parse_user_id


class InMemoryUsersRepo:
    def __init__(self) -> None:
        self._by_id: dict[str, User] = {}
        self._by_discord: dict[str, User] = {}
        self._counter = count(1)

    async def upsert(self, user: User) -> bool:
        key = str(user.user_id)
        self._by_id[key] = user
        if user.discord_id:
            self._by_discord[user.discord_id] = user
        return True

    async def get(self, user_id: str) -> User | None:
        return self._by_id.get(user_id)

    async def delete(self, user_id: str) -> bool:
        removed = self._by_id.pop(user_id, None)
        if removed and removed.discord_id:
            self._by_discord.pop(removed.discord_id, None)
        return removed is not None

    async def exists(self, user_id: str) -> bool:
        return user_id in self._by_id

    async def next_id(self) -> str:
        return f"USER{next(self._counter):04d}"

    async def get_by_discord_id(self, discord_id: str) -> User | None:
        return self._by_discord.get(discord_id)


class InMemoryCharactersRepo:
    def __init__(self) -> None:
        self._by_id: dict[str, Character] = {}
        self._counter = count(1)

    async def get(self, character_id: str) -> Character | None:
        return self._by_id.get(character_id)

    async def upsert(self, character: Character) -> bool:
        self._by_id[character.character_id] = character
        return True

    async def delete(self, character_id: str) -> bool:
        return self._by_id.pop(character_id, None) is not None

    async def next_id(self) -> str:
        return f"CHAR{next(self._counter):04d}"

    async def exists(self, character_id: str) -> bool:
        return character_id in self._by_id


class StubIdService:
    def __init__(self) -> None:
        self._counter = count(1)
        self._map: dict[str, str] = {}

    async def next_quest_id(self) -> str:  # pragma: no cover - not used
        return "QST0001"

    async def next_summary_id(self) -> str:  # pragma: no cover - not used
        return "SUM0001"

    async def ensure_user_id(self, discord_id: str) -> str:
        if discord_id in self._map:
            return self._map[discord_id]
        user_id = f"USER{next(self._counter):04d}"
        self._map[discord_id] = user_id
        return user_id


class StubGuild:
    def __init__(self, guild_id: int) -> None:
        self.id = guild_id
        self.members: list[StubMember] = []
        self._roles: dict[int, SimpleNamespace] = {}

    def add_role(self, role_id: int, name: str) -> None:
        self._roles[role_id] = SimpleNamespace(id=role_id, mention=f"@{name}")

    def get_role(self, role_id: int):
        return self._roles.get(role_id)


class StubMember:
    def __init__(
        self,
        member_id: int,
        *,
        guild: StubGuild | None = None,
        bot: bool = False,
        joined_at: datetime | None = None,
    ) -> None:
        self.id = member_id
        self.guild = guild
        self.bot = bot
        self.joined_at = joined_at or datetime.now(timezone.utc)
        self.roles: list[SimpleNamespace] = []
        self.mention = f"<@{member_id}>"
        self.display_name = f"user-{member_id}"
        self.display_avatar = SimpleNamespace(url="https://example.com/avatar.png")
        if guild is not None:
            guild.members.append(self)


@pytest.mark.asyncio
async def test_user_provisioning_creates_new_user() -> None:
    users_repo = InMemoryUsersRepo()
    id_service = StubIdService()
    service = UserProvisioningService(users_repo=users_repo, id_service=id_service)
    guild = StubGuild(1)
    member = StubMember(42, guild=guild)

    result = await service.ensure_member_user(cast(discord.Member, member))

    assert result.created is True
    assert str(result.user.user_id) == "USER0001"
    assert result.user.roles == [Role.MEMBER]
    stored = await users_repo.get("USER0001")
    assert stored is not None
    assert stored.discord_id == str(member.id)


@pytest.mark.asyncio
async def test_user_provisioning_sync_skips_bots() -> None:
    users_repo = InMemoryUsersRepo()
    id_service = StubIdService()
    service = UserProvisioningService(users_repo=users_repo, id_service=id_service)
    guild = StubGuild(5)
    StubMember(1, guild=guild)
    StubMember(2, guild=guild, bot=True)

    stats = await service.sync_guild_members(cast(discord.Guild, guild))

    assert stats == SyncStats(processed=1, created=1)
    assert await users_repo.get("USER0001") is not None


@pytest.mark.asyncio
async def test_role_management_promotes_player() -> None:
    users_repo = InMemoryUsersRepo()
    id_service = StubIdService()
    provisioning = UserProvisioningService(users_repo=users_repo, id_service=id_service)
    guild = StubGuild(10)
    member = StubMember(99, guild=guild)
    await provisioning.ensure_member_user(
        cast(discord.Member, member)
    )  # create baseline user

    service = RoleManagementService(
        users_repo=users_repo, user_provisioning=provisioning
    )
    result = await service.grant_player(cast(discord.Member, member))

    assert result.status is PlayerRoleStatus.PROMOTED
    assert result.user.is_player is True
    reloaded = await users_repo.get(str(result.user.user_id))
    assert reloaded is not None and reloaded.is_player


@pytest.mark.asyncio
async def test_role_management_revoke_player_blocked_by_referee() -> None:
    users_repo = InMemoryUsersRepo()
    id_service = StubIdService()
    provisioning = UserProvisioningService(users_repo=users_repo, id_service=id_service)
    guild = StubGuild(11)
    member = StubMember(77, guild=guild)
    provision = await provisioning.ensure_member_user(cast(discord.Member, member))
    user = provision.user
    user.enable_player()
    user.enable_referee()
    await users_repo.upsert(user)

    service = RoleManagementService(
        users_repo=users_repo, user_provisioning=provisioning
    )
    result = await service.revoke_player(cast(discord.Member, member))

    assert result.status is PlayerRoleStatus.BLOCKED_REFEREE
    stored = await users_repo.get(str(user.user_id))
    assert stored is not None and stored.is_player and stored.is_referee


@pytest.mark.asyncio
async def test_role_management_revoke_referee() -> None:
    users_repo = InMemoryUsersRepo()
    id_service = StubIdService()
    provisioning = UserProvisioningService(users_repo=users_repo, id_service=id_service)
    guild = StubGuild(12)
    member = StubMember(101, guild=guild)
    provision = await provisioning.ensure_member_user(cast(discord.Member, member))
    user = provision.user
    user.enable_player()
    user.enable_referee()
    await users_repo.upsert(user)

    service = RoleManagementService(
        users_repo=users_repo, user_provisioning=provisioning
    )
    result = await service.revoke_referee(cast(discord.Member, member))

    assert result.status is RefereeRoleStatus.DEMOTED
    stored = await users_repo.get(str(user.user_id))
    assert stored is not None and stored.is_referee is False


@pytest.mark.asyncio
async def test_character_creation_requires_player_role() -> None:
    users_repo = InMemoryUsersRepo()
    characters_repo = InMemoryCharactersRepo()
    id_service = StubIdService()
    provisioning = UserProvisioningService(users_repo=users_repo, id_service=id_service)
    guild = StubGuild(20)
    member = StubMember(555, guild=guild)
    await provisioning.ensure_member_user(cast(discord.Member, member))

    service = CharacterCreationService(
        characters_repo=characters_repo,
        users_repo=users_repo,
        user_provisioning=provisioning,
    )

    payload = CharacterCreatePayload(
        name="Aria",
        ddb_link="https://ddb.example/aria",
        character_thread_link="https://discord.com/channels/thread",
        token_link="https://cdn.example/token.png",
        art_link="https://cdn.example/art.png",
    )

    with pytest.raises(PlayerRoleRequiredError):
        await service.create_for_member(cast(discord.Member, member), payload)


@pytest.mark.asyncio
async def test_character_creation_creates_record_and_links_user() -> None:
    users_repo = InMemoryUsersRepo()
    characters_repo = InMemoryCharactersRepo()
    id_service = StubIdService()
    provisioning = UserProvisioningService(users_repo=users_repo, id_service=id_service)
    guild = StubGuild(21)
    member = StubMember(900, guild=guild)
    provision = await provisioning.ensure_member_user(cast(discord.Member, member))
    user = provision.user
    user.enable_player()
    user.player = user.player or Player()
    await users_repo.upsert(user)

    service = CharacterCreationService(
        characters_repo=characters_repo,
        users_repo=users_repo,
        user_provisioning=provisioning,
    )

    payload = CharacterCreatePayload(
        name="Nova",
        ddb_link="https://ddb.example/nova",
        character_thread_link="https://discord.com/channels/thread",
        token_link="https://cdn.example/token.png",
        art_link="https://cdn.example/art.png",
        tags=["wizard"],
    )

    result = await service.create_for_member(cast(discord.Member, member), payload)

    assert result.character.name == "Nova"
    assert result.character.character_id == "CHAR0001"
    stored_character = await characters_repo.get("CHAR0001")
    assert stored_character is not None
    updated_user = await users_repo.get(str(result.user.user_id))
    assert updated_user is not None
    assert updated_user.player is not None
    assert str(updated_user.player.characters[0]) == result.character.character_id


@pytest.mark.asyncio
async def test_character_success_embed_includes_resources() -> None:
    config = DiscordBotConfig(
        token="dummy",
        quest_channel_id=1,
        summary_channel_id=2,
        player_role_id=3,
        referee_role_id=4,
    )
    dummy_service = (
        CharacterCreationService(  # minimal service for constructor requirements
            characters_repo=InMemoryCharactersRepo(),
            users_repo=InMemoryUsersRepo(),
            user_provisioning=UserProvisioningService(
                users_repo=InMemoryUsersRepo(), id_service=StubIdService()
            ),
        )
    )
    cog = CharacterCommandsCog(service=dummy_service, config=config)

    user = User(
        user_id=parse_user_id("USER9999"),
        discord_id="9999",
        roles=[Role.PLAYER],
        player=Player(),
    )
    character = Character(
        owner_id=parse_user_id("USER9999"),
        character_id="CHAR4242",
        name="Kestrel",
        ddb_link="https://ddb.example/kestrel",
        character_thread_link="https://discord.com/channels/threads/123",
        token_link="https://cdn.example/token.png",
        art_link="https://cdn.example/art.png",
        created_at=datetime.now(timezone.utc),
    )
    result = CharacterCreationResult(character=character, user=user)
    member = StubMember(999)

    embed = cog._success_embed(result, member)  # type: ignore[arg-type]

    assert embed.title == "Character created"
    assert embed.fields[1].value is not None and "D&D Beyond" in embed.fields[1].value
    assert embed.thumbnail.url == character.art_link
