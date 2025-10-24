import logging
from datetime import datetime, timezone
from typing import Optional

from discord import Guild, Member, Message, RawReactionActionEvent, VoiceState
from discord.ext import commands

from ..database import db_client
from ...domain.models.UserModel import User
from ..services.user_registry import UserRegistry

class ListnerCog(commands.Cog):

	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self._voice_sessions: dict[int, datetime] = {}
		self._user_registry = UserRegistry()
		self._clock = lambda: datetime.now(timezone.utc)

	async def _ensure_cached_user(self, member: Member) -> User:
		guild_id = member.guild.id
		guild_entry = self.bot.guild_data.get(guild_id)

		if guild_entry is None:
			await self.bot.load_or_create_guild_cache(member.guild)
			guild_entry = self.bot.guild_data[guild_id]

		users = guild_entry.setdefault("users", {})
		user = users.get(member.id)

		if user is None:
			user = await self._user_registry.ensure_member(member, guild_id)
			user.guild_id = guild_id
			users[member.id] = user

		return user

	async def _resolve_cached_user(
		self, guild: Guild, user_id: int
	) -> Optional[User]:
		guild_entry = self.bot.guild_data.get(guild.id)

		if guild_entry is None:
			await self.bot.load_or_create_guild_cache(guild)
			guild_entry = self.bot.guild_data[guild.id]

		users = guild_entry.setdefault("users", {})
		user = users.get(user_id)

		if user is not None:
			return user

		member = guild.get_member(user_id)
		if member is None:
			try:
				member = await guild.fetch_member(user_id)
			except Exception as exc:  # pragma: no cover - network edge
				logging.warning(
					"Unable to resolve guild member %s in %s: %s",
					user_id,
					guild.id,
					exc,
				)
				return None

		user = await self._user_registry.ensure_member(member, guild.id)
		user.guild_id = guild.id
		users[user_id] = user
		return user

	async def _resolve_message_author_id(
		self, guild: Guild, channel_id: int, message_id: int
	) -> Optional[int]:
		channel = guild.get_channel(channel_id)
		if channel is None:
			try:
				channel = await guild.fetch_channel(channel_id)
			except Exception as exc:  # pragma: no cover
				logging.warning(
					"Unable to resolve channel %s in guild %s: %s",
					channel_id,
					guild.id,
					exc,
				)
				return None

		try:
			message = await channel.fetch_message(message_id)
		except Exception as exc:  # pragma: no cover
			logging.warning(
				"Unable to fetch message %s in channel %s guild %s: %s",
				message_id,
				channel_id,
				guild.id,
				exc,
			)
			return None

		return message.author.id

	@commands.Cog.listener("on_member_join")
	async def _on_member_join(self, member: Member):

		if member.bot:
			return

		user = await self._user_registry.ensure_member(member, member.guild.id)
		user.guild_id = member.guild.id
		ensure_entry = getattr(self.bot, "_ensure_guild_entry", None)
		if callable(ensure_entry):
			guild_entry = ensure_entry(member.guild.id)
		else:
			guild_entry = self.bot.guild_data.setdefault(
				member.guild.id,
				{"db": db_client.get_database(str(member.guild.id)), "users": {}},
			)
		guild_entry.setdefault("users", {})[member.id] = user
		await self.bot.dirty_data.put((member.guild.id, member.id))
		logging.info(
			"User %s joined guild %s at %s (cached users=%d)",
			member.id,
			member.guild.id,
			member.joined_at,
			len(self.bot.guild_data[member.guild.id]["users"]),
		)

	@commands.Cog.listener("on_message")
	async def on_message(self, message: Message):

		if message.author.bot:
			return

		if message.guild is None:
			logging.debug("Skipping DM message from %s (no guild context)", message.author.id)
			return

		guild_id = message.guild.id
		author_id = message.author.id

		user = await self._ensure_cached_user(message.author)
		user.increment_messages_count()

		timestamp = message.created_at or self._clock()
		user.update_last_active(timestamp)

		await self.bot.dirty_data.put((guild_id, author_id))
		logging.info(
			"Processed message gid=%s uid=%s channel=%s total_messages=%d last_active=%s",
			guild_id,
			author_id,
			message.channel.id,
			user.messages_count_total,
			user.last_active_at,
		)

	@commands.Cog.listener("on_raw_reaction_add")
	async def _on_raw_reaction_add(self, reaction: RawReactionActionEvent):

		if reaction.member and reaction.member.bot:
			return

		if reaction.event_type != "REACTION_ADD":
			return

		if reaction.guild_id is None:
			logging.info(f"No guild ID in reaction: {reaction}")
			return

		guild_id = reaction.guild_id
		reacting_user_id = reaction.member.id if reaction.member else reaction.user_id

		guild = self.bot.get_guild(guild_id)
		if guild is None:
			logging.warning("Guild %s not found for reaction event", guild_id)
			return

		reacting_member = reaction.member
		if reacting_member is None:
			member_obj = guild.get_member(reacting_user_id)
			if member_obj is None:
				try:
					member_obj = await guild.fetch_member(reacting_user_id)
				except Exception as exc:  # pragma: no cover - network edge
					logging.warning(
						"Unable to resolve reacting member %s in guild %s: %s",
						reacting_user_id,
						guild_id,
						exc,
					)
					return
			reacting_member = member_obj
		reacting_user = await self._ensure_cached_user(reacting_member)
		reacting_user.increment_reactions_given()
		reacting_user.update_last_active(self._clock())

		author_id = await self._resolve_message_author_id(
			guild, reaction.channel_id, reaction.message_id
		)
		if author_id is None:
			await self.bot.dirty_data.put((guild_id, reacting_user_id))
			return

		author_user = await self._resolve_cached_user(guild, author_id)
		if author_user is None:
			return

		author_user.increment_reactions_received()

		await self.bot.dirty_data.put((guild_id, reacting_user_id))
		await self.bot.dirty_data.put((guild_id, author_id))
		logging.info(
			"Processed reaction %s gid=%s reactor=%s author=%s (given=%d received=%d)",
			reaction.emoji,
			guild_id,
			reacting_user_id,
			author_id,
			reacting_user.reactions_given,
			author_user.reactions_received,
		)

	@commands.Cog.listener("on_voice_state_update")
	async def _on_voice_state_update(
		self,
		member: Member,
		before: VoiceState,
		after: VoiceState
	):

		if member.bot:
			return

		user = await self._ensure_cached_user(member)
		user.update_last_active(self._clock())

		now = self._clock()
		session_start = self._voice_sessions.get(member.id)

		if before.channel is None and after.channel is not None:
			self._voice_sessions[member.id] = now

		elif before.channel is not None and after.channel is None:
			if session_start:
				seconds = int((now - session_start).total_seconds())
				if seconds > 0:
					user.add_voice_time_spent(seconds)
			self._voice_sessions.pop(member.id, None)

		elif before.channel is not None and after.channel is not None:
			if session_start:
				seconds = int((now - session_start).total_seconds())
				if seconds > 0:
					user.add_voice_time_spent(seconds)
			self._voice_sessions[member.id] = now

		else:
			logging.warning(
				"Unexpected voice update for %s (before=%s, after=%s)",
				member.id,
				before.channel,
				after.channel,
			)
			return

		await self.bot.dirty_data.put((member.guild.id, member.id))
		logging.info(
			"Voice state update gid=%s uid=%s before=%s after=%s total_hours=%.2f",
			member.guild.id,
			member.id,
			getattr(before.channel, "id", None),
			getattr(after.channel, "id", None),
			user.voice_total_time_spent,
		)

	@commands.Cog.listener("on_guild_join")
	async def _on_guild_join(self, guild: Guild):
		"""When joining a guild:
		- Scrape and create Users from Guild.Members
		- Create database for new guild
		- Save all data to cache"""

		logging.info(f"Joined new guild: {guild.name} (ID: {guild.id})")

		users = {}
		for member in guild.members:

			if member.bot:
				continue

			logging.info("Caching user for guild join %s (ID: %s)", member.name, member.id)
			user = await self._user_registry.ensure_member(member)
			users[member.id] = user

			await self.bot.dirty_data.put((guild.id, member.id))


		db_name = f"{guild.id}"
		g_db = db_client.get_database(db_name)

		self.bot.guild_data[guild.id] = {
			"db": g_db,
			"users": users
		}
		logging.info(f"Cache created for guild {guild.name}.")

	@commands.Cog.listener("on_guild_remove")
	async def _on_guild_remove(self, guild: Guild):
		logging.info(f"Left guild: {guild.name} (ID: {guild.id}) \nRemoving cache...")
		self.bot.guild_data.pop(guild.id, None)
		logging.info(f"Removed caches for guild {guild.name}.")

	@commands.Cog.listener("on_error")
	async def _on_error(self, event_method, /, *args, **kwargs):
		logging.error(f"Error in {event_method}: {args} {kwargs}")
		await super().on_error(event_method, *args, **kwargs)

async def setup(bot: commands.Bot):
	await bot.add_cog(ListnerCog(bot))
