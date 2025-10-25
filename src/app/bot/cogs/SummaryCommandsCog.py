from __future__ import annotations

import logging
import re
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.services import guild_settings_store
from app.bot.utils.log_stream import send_demo_log
from app.domain.models.EntityIDModel import CharacterID, QuestID, SummaryID, UserID
from app.domain.models.SummaryModel import QuestSummary, SummaryKind, SummaryStatus
from app.domain.models.UserModel import User
from app.infra.mongo.users_repo import UsersRepoMongo
from app.infra.serialization import to_bson


class SummaryCommandsCog(commands.Cog):
	"""Slash commands for creating and updating quest summaries via DM."""

	summary = app_commands.Group(
		name="summary", description="Share quest summaries and open discussion threads."
	)

	def __init__(self, bot: commands.Bot) -> None:
		self.bot = bot
		self._users_repo = UsersRepoMongo()
		self._active_summary_sessions: Set[int] = set()
		self._demo_log = send_demo_log

	# ---------- Core helpers ----------

	async def _ensure_guild_cache(self, guild: discord.Guild) -> None:
		if guild.id not in self.bot.guild_data:
			await self.bot.load_or_create_guild_cache(guild)

	def _lookup_user_display(self, guild_id: int, user_id: Optional[UserID]) -> str:
		if user_id is None:
			return "Unknown"
		guild_entry = self.bot.guild_data.get(guild_id)
		if not guild_entry:
			return str(user_id)
		users = guild_entry.get("users", {})
		for cached in users.values():
			try:
				if cached.user_id == user_id:
					if cached.discord_id:
						return f"<@{cached.discord_id}>"
					return str(cached.user_id)
			except AttributeError:
				continue
		return str(user_id)

	async def _get_cached_user(self, member: discord.Member) -> User:
		await self._ensure_guild_cache(member.guild)
		guild_entry = self.bot.guild_data[member.guild.id]

		user = guild_entry["users"].get(member.id)
		if user is not None:
			return user

		listener: Optional[commands.Cog] = self.bot.get_cog("ListnerCog")
		if listener is None:
			raise RuntimeError("Listener cog not loaded; cannot resolve users.")

		ensure_method = getattr(listener, "_ensure_cached_user", None)
		if ensure_method is None:
			raise RuntimeError("Listener cog missing _ensure_cached_user helper.")

		user = await ensure_method(member)  # type: ignore[misc]
		return user

	def _summary_to_doc(self, summary: QuestSummary) -> dict:
		payload = to_bson(summary)
		payload["summary_id"] = {"value": str(summary.summary_id)}
		payload["guild_id"] = int(summary.guild_id)
		return payload

	def _parse_entity_id(self, cls, payload: object) -> Optional[object]:
		if payload is None:
			return None
		if isinstance(payload, cls):
			return payload
		if isinstance(payload, dict):
			value = payload.get("value")
			if isinstance(value, str) and value:
				return cls.parse(value)
			number = payload.get("number")
			if number is not None:
				prefix = payload.get("prefix", cls.prefix)
				return cls.parse(f"{prefix}{number}")
		if isinstance(payload, str) and payload:
			return cls.parse(payload)
		if isinstance(payload, int):
			return cls.parse(f"{cls.prefix}{payload}")
		return None

	def _summary_from_doc(self, guild_id: int, doc: dict) -> QuestSummary:
		summary_id = self._parse_entity_id(SummaryID, doc.get("summary_id")) or SummaryID.parse(
			str(doc.get("_id"))
		)
		kind_payload = doc.get("kind") or SummaryKind.PLAYER
		try:
			kind = kind_payload if isinstance(kind_payload, SummaryKind) else SummaryKind(kind_payload)
		except ValueError:
			kind = SummaryKind.PLAYER

		summary = QuestSummary(
			summary_id=summary_id,
			kind=kind,
			author_id=self._parse_entity_id(UserID, doc.get("author_id")),
			character_id=self._parse_entity_id(CharacterID, doc.get("character_id")),
			quest_id=self._parse_entity_id(QuestID, doc.get("quest_id")),
			guild_id=int(doc.get("guild_id", guild_id)),
			raw=doc.get("raw"),
			title=doc.get("title"),
			description=doc.get("description"),
			created_on=doc.get("created_on") or datetime.now(timezone.utc),
		)

		summary.last_edited_at = doc.get("last_edited_at")
		summary.players = [
			self._parse_entity_id(UserID, entry)
			for entry in doc.get("players", [])
			if self._parse_entity_id(UserID, entry) is not None
		]
		summary.characters = [
			self._parse_entity_id(CharacterID, entry)
			for entry in doc.get("characters", [])
			if self._parse_entity_id(CharacterID, entry) is not None
		]
		summary.linked_quests = [
			self._parse_entity_id(QuestID, entry)
			for entry in doc.get("linked_quests", [])
			if self._parse_entity_id(QuestID, entry) is not None
		]
		summary.linked_summaries = [
			self._parse_entity_id(SummaryID, entry)
			for entry in doc.get("linked_summaries", [])
			if self._parse_entity_id(SummaryID, entry) is not None
		]

		summary.channel_id = doc.get("channel_id")
		summary.message_id = doc.get("message_id")
		summary.thread_id = doc.get("thread_id")

		status_raw = doc.get("status")
		if status_raw:
			try:
				summary.status = status_raw if isinstance(status_raw, SummaryStatus) else SummaryStatus(status_raw)
			except ValueError:
				summary.status = SummaryStatus.POSTED

		return summary

	def _persist_summary(self, guild_id: int, summary: QuestSummary) -> None:
		summary.guild_id = guild_id
		guild_entry = self.bot.guild_data[guild_id]
		db = guild_entry["db"]
		payload = self._summary_to_doc(summary)
		db["summaries"].update_one(
			{"guild_id": guild_id, "summary_id.value": str(summary.summary_id)},
			{"$set": payload},
			upsert=True,
		)

	def _fetch_summary(self, guild_id: int, summary_id: SummaryID) -> Optional[QuestSummary]:
		guild_entry = self.bot.guild_data[guild_id]
		db = guild_entry["db"]
		doc = db["summaries"].find_one(
			{
				"guild_id": guild_id,
				"$or": [
					{"summary_id.value": str(summary_id)},
					{"_id": str(summary_id)},
				],
			}
		)
		if not doc:
			return None
		return self._summary_from_doc(guild_id, doc)

	def _next_summary_id(self, guild_id: int) -> SummaryID:
		guild_entry = self.bot.guild_data[guild_id]
		db = guild_entry["db"]
		coll = db["summaries"]
		while True:
			candidate = SummaryID.generate()
			exists = coll.count_documents(
				{"guild_id": guild_id, "summary_id.value": str(candidate)}, limit=1
			)
			if not exists:
				return candidate

	def _build_summary_embed(
		self,
		summary: QuestSummary,
		guild: discord.Guild,
		*,
		updated_at: Optional[datetime] = None,
	) -> discord.Embed:
		title = summary.title or f"Summary {summary.summary_id}"
		description = summary.description or "Summary details to follow in the thread."
		embed = discord.Embed(
			title=title,
			description=description,
			colour=discord.Colour.teal(),
			timestamp=updated_at or datetime.now(timezone.utc),
		)

		author_display = self._lookup_user_display(guild.id, summary.author_id)
		embed.add_field(name="Author", value=author_display, inline=False)

		if summary.characters:
			char_lines = [f"`{str(char_id)}`" for char_id in summary.characters]
			embed.add_field(
				name="Characters",
				value="\n".join(char_lines),
				inline=False,
			)

		if summary.linked_quests:
			quest_lines = [f"`{str(quest_id)}`" for quest_id in summary.linked_quests]
			embed.add_field(
				name="Linked Quests",
				value="\n".join(quest_lines),
				inline=False,
			)

		status_label = summary.status.value.title()
		embed.set_footer(text=f"Summary ID: {summary.summary_id} • Status: {status_label}")
		return embed

	async def _sync_summary_announcement(
		self,
		guild: discord.Guild,
		summary: QuestSummary,
		*,
		updated_at: Optional[datetime] = None,
	) -> None:
		if not summary.channel_id or not summary.message_id:
			return

		channel = guild.get_channel(int(summary.channel_id))
		if channel is None:
			try:
				channel = await guild.fetch_channel(int(summary.channel_id))
			except Exception as exc:  # pragma: no cover - defensive
				logging.debug(
					"Unable to resolve summary channel %s in guild %s: %s",
					summary.channel_id,
					guild.id,
					exc,
				)
				return

		try:
			message = await channel.fetch_message(int(summary.message_id))
		except Exception as exc:  # pragma: no cover - defensive
			logging.debug(
				"Unable to fetch summary message %s in guild %s: %s",
				summary.message_id,
				guild.id,
				exc,
			)
			return

		embed = self._build_summary_embed(summary, guild, updated_at=updated_at)

		try:
			await message.edit(embed=embed)
		except Exception as exc:  # pragma: no cover - defensive
			logging.debug(
				"Unable to update summary announcement %s in guild %s: %s",
				summary.summary_id,
				guild.id,
				exc,
			)

	async def _post_summary_announcement(
		self,
		interaction: discord.Interaction,
		summary: QuestSummary,
	) -> tuple[discord.Message, Optional[discord.Thread]]:
		settings = guild_settings_store.fetch_settings(interaction.guild.id) or {}
		channel_id = settings.get("summary_channel_id")
		if channel_id is None:
			raise ValueError(
				"No summary channel configured. Run `/setup summary` before posting summaries."
			)

		channel: Optional[discord.TextChannel] = None
		try:
			channel = interaction.guild.get_channel(int(channel_id))  # type: ignore[arg-type]
		except (TypeError, ValueError):
			channel = None
		if channel is None:
			try:
				channel = await interaction.guild.fetch_channel(int(channel_id))
			except Exception:
				channel = None
		if channel is None or not isinstance(channel, discord.TextChannel):
			raise ValueError("The configured summary channel is not accessible.")

		me = interaction.guild.me
		if me is None:
			raise ValueError("Unable to resolve bot member for permission checks.")
		perms = channel.permissions_for(me)
		if not perms.send_messages:
			raise ValueError(f"I need Send Messages permission in {channel.mention} to share summaries.")
		if not perms.create_public_threads and not perms.create_private_threads:
			raise ValueError(
				f"I need permission to create threads in {channel.mention} to open summary discussions."
			)

		embed = self._build_summary_embed(summary, interaction.guild)
		message = await channel.send(embed=embed)

		thread: Optional[discord.Thread] = None
		thread_name = f"Summary: {summary.title or summary.summary_id}"[:90]
		try:
			thread = await message.create_thread(
				name=thread_name,
				auto_archive_duration=1440,
			)
			await thread.send(
				"Thanks for sharing your summary! Post the full write-up, images, or links in this thread."
			)
		except Exception:
			thread = None

		return message, thread

	def _parse_character_ids(
		self,
		raw: str,
		allowed: Dict[str, CharacterID],
	) -> List[CharacterID]:
		tokens = [
			token.strip().upper()
			for token in re.split(r"[,\s]+", raw.strip())
			if token.strip()
		]
		if not tokens:
			return []

		characters: List[CharacterID] = []
		for token in tokens:
			if token not in allowed:
				raise ValueError(f"{token} is not one of your characters.")
			characters.append(allowed[token])
		return characters

	def _parse_quest_ids(self, raw: str) -> List[QuestID]:
		tokens = [
			token.strip().upper()
			for token in re.split(r"[,\s]+", raw.strip())
			if token.strip()
		]
		quests: List[QuestID] = []
		for token in tokens:
			try:
				quests.append(QuestID.parse(token))
			except ValueError:
				raise ValueError(f"Unable to parse quest ID `{token}`.")
		return quests

	async def _list_owned_characters(
		self, guild: discord.Guild, member: discord.Member
	) -> Dict[str, CharacterID]:
		await self._ensure_guild_cache(guild)
		guild_entry = self.bot.guild_data[guild.id]
		db = guild_entry["db"]
		owner_id = str(UserID.from_body(str(member.id)))
		cursor = (
			db["characters"]
			.find(
				{"owner_id.value": owner_id},
				{"_id": 0, "character_id": 1},
			)
			.limit(50)
		)
		owned: Dict[str, CharacterID] = {}
		for doc in cursor:
			payload = doc.get("character_id")
			try:
				char_id = self._parse_entity_id(CharacterID, payload)
			except ValueError:
				char_id = None
			if isinstance(char_id, CharacterID):
				owned[str(char_id)] = char_id
		return owned

	# ---------- Commands ----------

	@summary.command(name="create", description="Guide a DM flow to publish a quest summary.")
	@app_commands.guild_only()
	async def summary_create(self, interaction: discord.Interaction) -> None:
		if interaction.guild is None:
			await interaction.response.send_message(
				"This command can only be used inside a guild.", ephemeral=True
			)
			return

		member = interaction.user
		if not isinstance(member, discord.Member):
			await interaction.response.send_message(
				"Only guild members can create summaries.", ephemeral=True
			)
			return

		if member.id in self._active_summary_sessions:
			await interaction.response.send_message(
				"You already have an active summary session. Complete or cancel it before starting a new one.",
				ephemeral=True,
			)
			return

		try:
			user = await self._get_cached_user(member)
		except RuntimeError as exc:
			await interaction.response.send_message(str(exc), ephemeral=True)
			return

		owned_characters = await self._list_owned_characters(interaction.guild, member)
		if not owned_characters:
			await interaction.response.send_message(
				"You need at least one character before sharing a summary. Use `/character create` first.",
				ephemeral=True,
			)
			return

		await interaction.response.defer(ephemeral=True)
		self._active_summary_sessions.add(member.id)
		try:
			try:
				dm_channel = await member.create_dm()
			except discord.Forbidden:
				await interaction.followup.send(
					"I can't send you direct messages. Enable DMs from server members and run `/summary create` again.",
					ephemeral=True,
				)
				return

			session = SummaryCreationSession(
				self,
				interaction.guild,
				member,
				user,
				dm_channel,
				owned_characters,
			)
			try:
				result = await session.run()
			except RuntimeError as exc:
				await interaction.followup.send(str(exc), ephemeral=True)
				return

			if not result.success or result.summary is None:
				await interaction.followup.send(
					result.error or "Summary creation cancelled.",
					ephemeral=True,
				)
				return

			summary = result.summary
			summary.guild_id = interaction.guild.id
			summary.author_id = user.user_id
			summary.players = [user.user_id]
			summary.kind = SummaryKind.PLAYER
			summary.created_on = datetime.now(timezone.utc)
			summary.status = SummaryStatus.POSTED
			summary.validate_summary()

			try:
				message, thread = await self._post_summary_announcement(interaction, summary)
			except ValueError as exc:
				await interaction.followup.send(str(exc), ephemeral=True)
				return
			except Exception as exc:  # pragma: no cover - defensive
				logging.exception("Summary announce failed: %s", exc)
				await interaction.followup.send(
					"Unable to post the summary right now. Please try again shortly.",
					ephemeral=True,
				)
				return

			summary.channel_id = str(message.channel.id)
			summary.message_id = str(message.id)
			summary.thread_id = str(thread.id) if thread else None

			self._persist_summary(interaction.guild.id, summary)

			thread_notice = f"[discussion thread]({thread.jump_url})" if thread else "discussion thread"

			await interaction.followup.send(
				f"Summary `{summary.summary_id}` posted in {message.channel.mention}. "
				f"Continue the story in the {thread_notice}.",
				ephemeral=True,
			)

			try:
				await self._demo_log(
					self.bot,
					interaction.guild,
					f"{member.mention} published summary `{summary.summary_id}`",
				)
			except Exception:
				pass
		finally:
			self._active_summary_sessions.discard(member.id)

	@summary.command(name="edit", description="Update an existing summary via DM.")
	@app_commands.describe(summary="Summary ID (e.g. SUMMA1B2C3)")
	@app_commands.guild_only()
	async def summary_edit(self, interaction: discord.Interaction, summary: str) -> None:
		if interaction.guild is None:
			await interaction.response.send_message(
				"This command can only be used inside a guild.", ephemeral=True
			)
			return

		member = interaction.user
		if not isinstance(member, discord.Member):
			await interaction.response.send_message(
				"Only guild members can edit summaries.", ephemeral=True
			)
			return

		try:
			summary_id = SummaryID.parse(summary.upper())
		except ValueError as exc:
			await interaction.response.send_message(str(exc), ephemeral=True)
			return

		await self._ensure_guild_cache(interaction.guild)
		existing = self._fetch_summary(interaction.guild.id, summary_id)
		if existing is None:
			await interaction.response.send_message("Summary not found.", ephemeral=True)
			return

		try:
			user = await self._get_cached_user(member)
		except RuntimeError as exc:
			await interaction.response.send_message(str(exc), ephemeral=True)
			return

		if existing.author_id != user.user_id:
			await interaction.response.send_message(
				"Only the summary author can edit it.", ephemeral=True
			)
			return

		if member.id in self._active_summary_sessions:
			await interaction.response.send_message(
				"You already have an active summary session. Complete or cancel it before starting a new one.",
				ephemeral=True,
			)
			return

		owned_characters = await self._list_owned_characters(interaction.guild, member)
		if not owned_characters:
			await interaction.response.send_message(
				"You need at least one character before editing summaries.",
				ephemeral=True,
			)
			return

		await interaction.response.defer(ephemeral=True)
		self._active_summary_sessions.add(member.id)
		try:
			try:
				dm_channel = await member.create_dm()
			except discord.Forbidden:
				await interaction.followup.send(
					"I can't send you direct messages. Enable DMs from server members and run `/summary edit` again.",
					ephemeral=True,
				)
				return

			session = SummaryUpdateSession(
				self,
				interaction.guild,
				member,
				user,
				dm_channel,
				existing,
				owned_characters,
			)
			try:
				result = await session.run()
			except RuntimeError as exc:
				await interaction.followup.send(str(exc), ephemeral=True)
				return

			if not result.success or result.summary is None:
				await interaction.followup.send(
					result.error or "Summary update cancelled.",
					ephemeral=True,
				)
				return

			result.summary.last_edited_at = datetime.now(timezone.utc)
			result.summary.validate_summary()
			self._persist_summary(interaction.guild.id, result.summary)

			if result.summary.channel_id and result.summary.message_id:
				await self._sync_summary_announcement(
					interaction.guild,
					result.summary,
					updated_at=result.summary.last_edited_at,
				)

			await interaction.followup.send(
				f"Summary `{result.summary.summary_id}` updated.",
				ephemeral=True,
			)
		finally:
			self._active_summary_sessions.discard(member.id)


# ---------- DM session helpers ----------


@dataclass
class SummaryCreationResult:
	success: bool
	summary: Optional[QuestSummary] = None
	error: Optional[str] = None


@dataclass
class SummaryUpdateResult:
	success: bool
	summary: Optional[QuestSummary] = None
	error: Optional[str] = None


class SummarySessionBase:
	def __init__(
		self,
		cog: "SummaryCommandsCog",
		guild: discord.Guild,
		member: discord.Member,
		user: User,
		dm_channel: discord.DMChannel,
		owned_characters: Dict[str, CharacterID],
	) -> None:
		self.cog = cog
		self.guild = guild
		self.member = member
		self.user = user
		self.dm = dm_channel
		self.owned_characters = owned_characters
		self.timeout = 300
		self._preview_message: Optional[discord.Message] = None

	async def _safe_send(
		self,
		content: Optional[str] = None,
		*,
		embed: Optional[discord.Embed] = None,
	) -> discord.Message:
		try:
			return await self.dm.send(content=content, embed=embed)
		except discord.Forbidden as exc:
			raise RuntimeError(
				"I can't send you direct messages anymore. Enable DMs and run the command again."
			) from exc
		except discord.HTTPException as exc:
			raise RuntimeError(f"Failed to send DM: {exc}") from exc

	async def _ask(
		self,
		prompt: str,
		*,
		required: bool,
		allow_skip: bool = False,
		allow_clear: bool = False,
	) -> Optional[str]:
		instructions = ["Type `cancel` to stop."]
		if allow_skip:
			instructions.append("Type `skip` to keep the current value.")
		if allow_clear:
			instructions.append("Type `clear` to remove this value.")
		await self._safe_send(f"{prompt}\n" + " ".join(instructions))

		while True:
			try:
				message = await self.cog.bot.wait_for(
					"message",
					timeout=self.timeout,
					check=lambda m: m.author.id == self.member.id and m.channel.id == self.dm.id,
				)
			except asyncio.TimeoutError as exc:
				raise TimeoutError from exc

			content = message.content.strip()
			lower = content.lower()
			if lower == "cancel":
				raise RuntimeError("cancelled")
			if allow_clear and lower == "clear":
				return ""
			if allow_skip and lower == "skip":
				return None
			if not content:
				if required:
					await self._safe_send("Please provide a response, or type `cancel`.")
					continue
				return None
			return content

	def _build_preview_embed(self, summary: QuestSummary) -> discord.Embed:
		return self.cog._build_summary_embed(summary, self.guild)

	async def _update_preview(self, summary: QuestSummary) -> None:
		embed = self._build_preview_embed(summary)
		if self._preview_message is None:
			self._preview_message = await self._safe_send("**Current summary preview:**", embed=embed)
			return
		try:
			await self._preview_message.edit(embed=embed)
		except discord.HTTPException:
			self._preview_message = await self._safe_send("**Current summary preview:**", embed=embed)

	def _format_owned_characters(self) -> str:
		return ", ".join(f"`{cid}`" for cid in self.owned_characters.keys())


class SummaryCreationSession(SummarySessionBase):
	async def run(self) -> SummaryCreationResult:
		summary_id = self.cog._next_summary_id(self.guild.id)
		summary = QuestSummary(
			summary_id=summary_id,
			guild_id=self.guild.id,
			author_id=self.user.user_id,
			title=None,
			description=None,
			raw=None,
		)

		try:
			await self._safe_send(
				f"Let's share a quest summary! We'll post it automatically once the setup finishes.\n"
				f"Owned characters: {self._format_owned_characters()}"
			)

			title = await self._ask("**Step 1:** What's the summary title?", required=True)
			summary.title = title.strip()
			await self._update_preview(summary)

			quests_input = await self._ask(
				"**Step 2:** List quest IDs involved (comma or space separated), or `skip`.",
				required=False,
				allow_skip=True,
			)
			if quests_input:
				try:
					summary.linked_quests = self.cog._parse_quest_ids(quests_input)
				except ValueError as exc:
					return SummaryCreationResult(False, error=str(exc))
			await self._update_preview(summary)

			characters_input = await self._ask(
				"**Step 3:** Which of your characters were involved? Provide IDs separated by commas or spaces.",
				required=True,
			)
			try:
				summary.characters = self.cog._parse_character_ids(
					characters_input,
					self.owned_characters,
				)
			except ValueError as exc:
				return SummaryCreationResult(False, error=str(exc))
			if summary.characters:
				summary.character_id = summary.characters[0]
			await self._update_preview(summary)

			tldr_input = await self._ask(
				"**Step 4:** Share a quick TL;DR for the announcement (or `skip`).",
				required=False,
				allow_skip=True,
			)
			if tldr_input is not None:
				summary.description = tldr_input.strip() or None
			await self._update_preview(summary)
		except TimeoutError:
			return SummaryCreationResult(
				False,
				error="Timed out waiting for a response. Run `/summary create` again when you're ready.",
			)
		except RuntimeError as exc:
			return SummaryCreationResult(False, error=str(exc))

		summary.description = summary.description or "Story continues in the thread."
		summary.raw = summary.description
		return SummaryCreationResult(True, summary=summary)


class SummaryUpdateSession(SummarySessionBase):
	def __init__(
		self,
		cog: "SummaryCommandsCog",
		guild: discord.Guild,
		member: discord.Member,
		user: User,
		dm_channel: discord.DMChannel,
		summary: QuestSummary,
		owned_characters: Dict[str, CharacterID],
	) -> None:
		super().__init__(cog, guild, member, user, dm_channel, owned_characters)
		self.summary = summary

	async def run(self) -> SummaryUpdateResult:
		try:
			await self._safe_send("Let's update your summary. Respond with new values or `skip` to keep existing.")
			await self._update_preview(self.summary)

			title = await self._ask(
				"**Step 1:** Update the title (or `skip`, `clear`).",
				required=False,
				allow_skip=True,
				allow_clear=True,
			)
			if title not in (None, ""):
				self.summary.title = title.strip()
			elif title == "":
				self.summary.title = None
			await self._update_preview(self.summary)

			quests_input = await self._ask(
				"**Step 2:** Update linked quests (comma/space separated, `skip`, `clear`).",
				required=False,
				allow_skip=True,
				allow_clear=True,
			)
			if quests_input is not None:
				if quests_input == "":
					self.summary.linked_quests = []
				else:
					try:
						self.summary.linked_quests = self.cog._parse_quest_ids(quests_input)
					except ValueError as exc:
						return SummaryUpdateResult(False, error=str(exc))
			await self._update_preview(self.summary)

			characters_input = await self._ask(
				"**Step 3:** Update characters (comma/space separated, `skip`, `clear`).",
				required=False,
				allow_skip=True,
				allow_clear=True,
			)
			if characters_input is not None:
				if characters_input == "":
					self.summary.characters = []
				else:
					try:
						characters = self.cog._parse_character_ids(
							characters_input,
							self.owned_characters,
						)
					except ValueError as exc:
						return SummaryUpdateResult(False, error=str(exc))
					self.summary.characters = characters
					self.summary.character_id = characters[0] if characters else None
			await self._update_preview(self.summary)

			tldr_input = await self._ask(
				"**Step 4:** Update TL;DR (`skip`, `clear`).",
				required=False,
				allow_skip=True,
				allow_clear=True,
			)
			if tldr_input is not None:
				if tldr_input == "":
					self.summary.description = None
				else:
					self.summary.description = tldr_input.strip()
			await self._update_preview(self.summary)
		except TimeoutError:
			return SummaryUpdateResult(
				False,
				error="Timed out waiting for a response. Run `/summary edit` again when you're ready.",
			)
		except RuntimeError as exc:
			return SummaryUpdateResult(False, error=str(exc))

		self.summary.description = self.summary.description or "Story continues in the thread."
		self.summary.raw = self.summary.description
		return SummaryUpdateResult(True, summary=self.summary)


async def setup(bot: commands.Bot):
	await bot.add_cog(SummaryCommandsCog(bot))
