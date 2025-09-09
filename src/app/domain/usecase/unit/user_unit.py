from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from app.domain.models.CharacterModel import Character

# Domain Imports
from app.domain.models.EntityIDModel import CharacterID, UserID
from app.domain.models.UserModel import User

# Adding ports
from app.domain.usecase.ports import CharactersRepo, UsersRepo

# ------- CRUD Operations -------


def create_user(
    users_repo: UsersRepo,
    discord_id: str = None,
    dm_channel_id: str = None,
    joined_at: datetime = None,
) -> User:
    """
    Creates a new user from parameters.
    """

    user = User(
        user_id=users_repo.next_id(),
        discord_id=discord_id,
        dm_channel_id=dm_channel_id,
        joined_at=joined_at,
        last_active_at=None,
    )

    user.validate_user()

    users_repo.upsert(user)

    return user


def get_user(users_repo: UsersRepo, user_id: UserID) -> User:
    """
    Fetches a user by its ID.
    Raises ValueError if user does not exist.
    """

    if not users_repo.exists(user_id):
        raise ValueError(f"User ID does not exist: {user_id}")

    user: User = users_repo.get(user_id)

    return user


def get_user_by_discord_id(users_repo: UsersRepo, discord_id: str) -> User:
    """
    Fetches a user by their Discord ID.
    Raises ValueError if user does not exist.
    """

    user: User = users_repo.get_by_discord_id(discord_id)

    if user is None:
        raise ValueError(f"User with Discord ID does not exist: {discord_id}")

    return user


def update_user(
    users_repo: UsersRepo,
    user_id: UserID,
    discord_id: str = None,
    dm_channel_id: str = None,
    joined_at: datetime = None,
    last_active_at: datetime = None,
) -> User:
    """
    Updates an existing user with new parameters.
    Raises ValueError if user does not exist.
    """

    user = get_user(users_repo, user_id)

    if discord_id is not None:
        user.discord_id = discord_id

    if dm_channel_id is not None:
        user.dm_channel_id = dm_channel_id

    if joined_at is not None:
        user.joined_at = joined_at

    if last_active_at is not None:
        user.last_active_at = last_active_at

    user.validate_user()

    users_repo.upsert(user)

    return user


def delete_user(users_repo: UsersRepo, user_id: UserID) -> None:
    """
    Deletes a user by its ID.
    Raises ValueError if user does not exist.
    """

    if not users_repo.exists(user_id):
        raise ValueError(f"User ID does not exist: {user_id}")

    users_repo.delete(user_id)


# ------- Role Operations -------


def enable_player_role(users_repo: UsersRepo, user_id: UserID) -> User:
    """
    Enables the PLAYER role for a user.
    Raises ValueError if user does not exist.
    """

    user = get_user(users_repo, user_id)

    user.enable_player()

    users_repo.upsert(user)

    return user


def disable_player_role(users_repo: UsersRepo, user_id: UserID) -> User:
    """
    Disables the PLAYER role for a user.
    Raises ValueError if user does not exist or if user is a REFEREE.
    """

    user = get_user(users_repo, user_id)

    if user.is_referee:
        raise ValueError("Cannot disable PLAYER role for a REFEREE user.")

    user.disable_player()

    users_repo.upsert(user)

    return user


def enable_referee_role(users_repo: UsersRepo, user_id: UserID) -> User:
    """
    Enables the REFEREE role for a user.
    Raises ValueError if user does not exist.
    """

    user = get_user(users_repo, user_id)

    user.enable_referee()

    users_repo.upsert(user)

    return user


def disable_referee_role(users_repo: UsersRepo, user_id: UserID) -> User:
    """
    Disables the REFEREE role for a user.
    Raises ValueError if user does not exist.
    """

    user = get_user(users_repo, user_id)

    user.disable_referee()

    users_repo.upsert(user)

    return user


# ------- Link Character Operations -------


def link_character_to_user(
    users_repo: UsersRepo,
    characters_repo: CharactersRepo,
    user_id: UserID,
    character_id: CharacterID,
) -> Tuple[User, Character]:
    """
    Links a character to a user.
    Raises ValueError if user or character does not exist, or if user is not the owner of the character.
    """

    user: User = get_user(users_repo, user_id)

    if not characters_repo.exists(character_id):
        raise ValueError(f"Character ID does not exist: {character_id}")

    character: Character = characters_repo.get(character_id)

    if character.owner_id != user_id:
        raise ValueError(f"User {user_id} is not the owner of character {character_id}")

    if not user.is_player:
        raise ValueError(f"User {user_id} is not a player")

    if user.player is None:
        user.enable_player()

    if character_id in user.player.characters:
        raise ValueError(
            f"Character {character_id} is already linked to user {user_id}"
        )

    user.player.characters.append(character_id)

    user.player.validate_player()

    user.validate_user()

    users_repo.upsert(user)

    return user, character


def unlink_character_from_user(
    users_repo: UsersRepo,
    characters_repo: CharactersRepo,
    user_id: UserID,
    character_id: CharacterID,
) -> Tuple[User, Character]:
    """
    Unlinks a character from a user.
    Raises ValueError if user or character does not exist, if user is not the owner of the character, or if character not linked.
    """

    user: User = get_user(users_repo, user_id)

    if not characters_repo.exists(character_id):
        raise ValueError(f"Character ID does not exist: {character_id}")

    character: Character = characters_repo.get(character_id)

    if character.owner_id != user_id:
        raise ValueError(f"User {user_id} is not the owner of character {character_id}")

    if user.player is None or character_id not in user.player.characters:
        raise ValueError(f"Character {character_id} is not linked to user {user_id}")

    user.player.characters.remove(character_id)

    user.player.validate_player()

    user.validate_user()

    users_repo.upsert(user)

    return user, character


# ------- Telemetry -------


def update_user_last_active(
    users_repo: UsersRepo, user_id: UserID, last_active_at: datetime = None
) -> User:
    """
    Updates the last active timestamp for a user.
    Raises ValueError if user does not exist.
    """

    user = get_user(users_repo, user_id)

    if last_active_at is None:
        last_active_at = datetime.now(timezone.utc)

    user.last_active_at = last_active_at

    users_repo.upsert(user)

    return user


def update_player_last_active(
    users_repo: UsersRepo, user_id: UserID, last_active_at: datetime = None
) -> User:
    """
    Updates the last active timestamp for a player user.
    Raises ValueError if user does not exist or is not a player.
    """

    user = get_user(users_repo, user_id)

    if not user.is_player:
        raise ValueError(f"User {user_id} is not a player")

    if last_active_at is None:
        last_active_at = datetime.now(timezone.utc)

    user.last_active_at = last_active_at

    users_repo.upsert(user)

    return user


def update_referee_last_active(
    users_repo: UsersRepo, user_id: UserID, last_active_at: datetime = None
) -> User:
    """
    Updates the last active timestamp for a referee user.
    Raises ValueError if user does not exist or is not a referee.
    """

    user = get_user(users_repo, user_id)

    if not user.is_referee:
        raise ValueError(f"User {user_id} is not a referee")

    if last_active_at is None:
        last_active_at = datetime.now(timezone.utc)

    user.last_active_at = last_active_at

    users_repo.upsert(user)

    return user
