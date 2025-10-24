from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable, Optional

from discord import Member

from app.domain.models.EntityIDModel import UserID
from app.domain.models.UserModel import Role, User
from app.infra.mongo.users_repo import UsersRepoMongo


class UserRegistry:
	"""Adapter that keeps domain users in sync with Discord members.

	The registry wraps the Mongo-backed repo so the bot can create or fetch
	user records during gateway events without duplicating ID allocation or
	validation logic throughout the codebase.
	"""

	def __init__(
		self,
		users_repo: Optional[UsersRepoMongo] = None,
		*,
		clock: Optional[Callable[[], datetime]] = None,
	) -> None:
		self._users_repo = users_repo or UsersRepoMongo()
		self._clock = clock or (lambda: datetime.now(timezone.utc))

	async def ensure_member(
		self, member: Member, guild_id: Optional[int] = None
	) -> User:
		"""Return a domain user for the Discord member, creating it if needed."""
		if member.bot:
			raise ValueError("Bots are not tracked as users")

		resolved_guild_id = guild_id or getattr(member.guild, "id", None)
		if resolved_guild_id is None:
			raise ValueError("Guild id is required to ensure a member record")

		discord_id = str(member.id)
		existing = await self._users_repo.get_by_discord_id(
			int(resolved_guild_id), discord_id
		)
		if existing:
			if existing.guild_id != resolved_guild_id:
				existing.guild_id = resolved_guild_id
			return existing

		joined_at = member.joined_at or self._clock()

		user = User(
			user_id=UserID.from_body(str(member.id)),
			guild_id=resolved_guild_id,
			discord_id=discord_id,
			dm_channel_id=None,
			roles=[Role.MEMBER],
			dm_opt_in=True,
			joined_at=joined_at,
			last_active_at=joined_at,
		)

		user.validate_user()
		await self._users_repo.upsert(int(resolved_guild_id), user)
		return user

	async def touch_last_active(
		self, guild_id: int, user: User, *, active_at: Optional[datetime] = None
	) -> User:
		"""Update the cached user's last active timestamp and persist."""
		timestamp = active_at or self._clock()
		updated = replace(user, last_active_at=timestamp)
		updated.guild_id = guild_id
		updated.validate_user()
		await self._users_repo.upsert(int(guild_id), updated)
		return updated
