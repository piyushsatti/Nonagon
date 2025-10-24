import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

import discord
from discord.ext import commands

from app.infra.mongo.guild_adapter import upsert_user_sync
from app.infra.serialization import to_bson

from ..domain.models.UserModel import User
from .config import BOT_FLUSH_VIA_ADAPTER, BOT_TOKEN
from .database import db_client


class Nonagon(commands.Bot):
	"""Main bot class that initializes the Discord bot and loads cogs.
	This class is responsible for setting up the bot, registering events,
	and loading the necessary cogs for functionality.
	"""

	def __init__(
		self, intents: discord.Intents, *, primary_guild_id: Optional[int] = None
	):
		super().__init__(command_prefix=commands.when_mentioned, intents=intents)
		self.guild_data: dict[int, dict[str, Any]] = {}
		self.dirty_data: asyncio.Queue[tuple[int, int]] = asyncio.Queue()
		self.primary_guild_id = primary_guild_id

	# Called before the bot logins to discord
	async def setup_hook(self):

		# Load every .py file under the bot/cogs directory as an extension
		cogs_path = Path(__file__).parent / "cogs"
		loaded: list[str] = []
		failed: dict[str, str] = {}
		for file in cogs_path.glob("*.py"):
			if file.name.startswith("_"):
				continue  # skip __init__.py and private modules
			ext = f"app.bot.cogs.{file.stem}"  # e.g. bot.cogs.my_cog
			try:
				await self.load_extension(ext)
				loaded.append(ext)
				logging.info(f"Loaded extension {ext}")
			except Exception:
				import traceback as _tb

				failed[ext] = _tb.format_exc()
				logging.error("Error loading extension %s:\n%s", ext, failed[ext])

		diagnostics_ext = "app.bot.commands.diagnostics"
		if diagnostics_ext not in self.extensions:
			try:
				await self.load_extension(diagnostics_ext)
				loaded.append(diagnostics_ext)
				logging.info("Loaded extension %s", diagnostics_ext)
			except Exception:
				import traceback as _tb

				failed[diagnostics_ext] = _tb.format_exc()
				logging.error(
					"Error loading extension %s:\n%s",
					diagnostics_ext,
					failed[diagnostics_ext],
				)

		# Cog loader audit summary
		logging.info("Cog loader audit: %d loaded, %d failed", len(loaded), len(failed))
		if loaded:
			logging.info("Loaded cogs: %s", ", ".join(sorted(loaded)))
		if failed:
			for ext, tb in failed.items():
				logging.debug("Failed cog %s trace:\n%s", ext, tb)

		try:
			self.loop.create_task(self._auto_persist_loop())
		except Exception as e:
			logging.error(f"Auto persist loop encountered an error: {e}")

		await self._sync_application_commands()

		# Call the parent setup_hook to ensure all cogs are loaded
		await super().setup_hook()

	# Called to login and connect the bot to Discord
	async def start(self, BOT_TOKEN):
		async def _idle_forever(reason: str) -> None:
			logging.error(
				"%s. Bot will remain idle until restarted with valid credentials.",
				reason,
			)
			while True:
				await asyncio.sleep(30)

		normalized = (BOT_TOKEN or "").strip()
		placeholders = {"", "replace_me"}

		if normalized.lower() in placeholders:
			await _idle_forever(
				"BOT_TOKEN is missing or still set to the placeholder value"
			)
			return

		try:
			await super().start(normalized)
		except discord.LoginFailure as exc:
			await _idle_forever(f"Discord login failed: {exc}")
		except discord.HTTPException as exc:
			await _idle_forever(f"Discord HTTP error during startup: {exc}")
		except Exception as exc:  # pragma: no cover - defensive fallback
			await _idle_forever(f"Unexpected error during startup: {exc}")

	# Called when the bot is ready
	async def on_ready(self):
		await self._load_cache()
		tree_commands = [cmd.qualified_name for cmd in self.tree.get_commands()]
		logging.info("Logged in as %s (ID: %s)", self.user, self.user.id)
		logging.info("Loaded cogs: %s", ", ".join(sorted(self.cogs.keys())))
		logging.info("Slash commands: %s", ", ".join(sorted(tree_commands)))

	async def on_error(self, event_method, /, *args, **kwargs):
		await super().on_error(event_method, *args, **kwargs)

	def _ensure_guild_entry(self, guild_id: int) -> dict[str, Any]:
		entry = self.guild_data.get(guild_id)
		if entry is None:
			entry = {
				"guild_id": guild_id,
				"db": db_client.get_database(str(guild_id)),
				"users": {},
				"quests": {},
				"characters": {},
				"summaries": {},
			}
			self.guild_data[guild_id] = entry
		else:
			entry.setdefault("guild_id", guild_id)
			entry.setdefault("db", db_client.get_database(str(guild_id)))
			entry.setdefault("users", {})
			entry.setdefault("quests", {})
			entry.setdefault("characters", {})
			entry.setdefault("summaries", {})
		return entry

	async def _load_cache(self):
		logging.info("Loading guild caches…")
		tasks = [self.load_or_create_guild_cache(g) for g in self.guilds]
		await asyncio.gather(*tasks)
		logging.info("All guild caches ready.")

	async def _auto_persist_loop(self):
		"""Periodically flush *all* in-memory user caches back to MongoDB."""
		logging.info("Starting auto persist loop...")
		while not self.is_closed():
			await asyncio.sleep(15)
			logging.info("Flushing dirty user data to MongoDB...")
			to_flush: dict[tuple[int, int], User] = {}
			try:
				while True:
					gid, uid = self.dirty_data.get_nowait()
					guild_entry = self.guild_data.get(gid)
					if guild_entry is None:
						logging.debug(
							"Skipping flush for gid=%s uid=%s (no guild cache)", gid, uid
						)
						continue
					user = guild_entry.get("users", {}).get(uid)
					if user is None:
						logging.debug(
							"Skipping flush for gid=%s uid=%s (user missing in cache)",
							gid,
							uid,
						)
						continue
					to_flush[(gid, uid)] = user
			except asyncio.QueueEmpty:
				pass

			logging.info("Flushing %d user records to MongoDB", len(to_flush))
			for (gid, uid), user in to_flush.items():
				guild_entry = self.guild_data.get(gid)
				if guild_entry is None:
					logging.debug(
						"Skipping flush for gid=%s uid=%s (guild missing)", gid, uid
					)
					continue

				try:
					user.guild_id = gid
					if BOT_FLUSH_VIA_ADAPTER:
						await asyncio.to_thread(upsert_user_sync, db_client, gid, user)
					else:
						db = guild_entry["db"]
						payload = to_bson(user)
						payload["guild_id"] = payload.get("guild_id") or gid
						await asyncio.to_thread(
							db.users.update_one,
							{
								"guild_id": payload["guild_id"],
								"user_id.value": str(user.user_id),
							},
							{"$set": payload},
							upsert=True,
						)
					logging.debug(
						"Persisted gid=%s uid=%s as user_id=%s", gid, uid, user.user_id
					)
				except Exception as exc:  # pragma: no cover - defensive logging
					logging.exception(
						"Failed to persist gid=%s uid=%s user_id=%s: %s",
						gid,
						uid,
						user.user_id,
						exc,
					)
			logging.info("Completed user flush cycle (%d items)", len(to_flush))

	async def _sync_application_commands(self) -> None:
		try:
			if self.primary_guild_id:
				guild_obj = discord.Object(id=self.primary_guild_id)
				guild_commands = await self.tree.sync(guild=guild_obj)
				logging.info(
					"Synced %d slash commands to guild %s",
					len(guild_commands),
					self.primary_guild_id,
				)
			global_commands = await self.tree.sync()
			logging.info("Synced %d global slash commands", len(global_commands))
			for guild in self.guilds:
				try:
					scoped_commands = await self.tree.sync(
						guild=discord.Object(id=guild.id)
					)
					logging.info(
						"Synced %d slash commands to guild %s",
						len(scoped_commands),
						guild.id,
					)
				except Exception:
					logging.exception(
						"Failed to sync application commands for guild %s", guild.id
					)
		except Exception:
			logging.exception("Failed to sync application commands")

	async def load_or_create_guild_cache(self, guild: discord.Guild) -> None:
		db_name = f"{guild.id}"
		entry = self._ensure_guild_entry(guild.id)
		g_db = entry["db"]

		if db_name in db_client.list_database_names():
			logging.info(f"Loading cached users for {guild.name}")
			users: dict[int, User] = {}
			found_with_guild = False
			primary_cursor = g_db.users.find({"guild_id": guild.id}, {"_id": 0})
			for doc in primary_cursor:
				found_with_guild = True
				user = User.from_dict(doc)
				user.guild_id = guild.id
				raw_key = doc.get("discord_id") or user.discord_id
				if raw_key is None:
					logging.debug(
						"Skipping cached user with missing discord_id (guild=%s, user_id=%s)",
						guild.id,
						user.user_id,
					)
					continue
				try:
					key = int(raw_key)
				except (TypeError, ValueError):
					logging.debug(
						"Skipping cached user with non-numeric discord_id=%s (guild=%s, user_id=%s)",
						raw_key,
						guild.id,
						user.user_id,
					)
					continue
				users[key] = user

			if not found_with_guild:
				legacy_cursor = g_db.users.find({}, {"_id": 0})
				for doc in legacy_cursor:
					user = User.from_dict(doc)
					user.guild_id = guild.id
					raw_key = doc.get("discord_id") or user.discord_id
					if raw_key is None:
						logging.debug(
							"Skipping legacy user with missing discord_id (guild=%s, user_id=%s)",
							guild.id,
							user.user_id,
						)
						continue
					try:
						key = int(raw_key)
					except (TypeError, ValueError):
						logging.debug(
							"Skipping legacy user with non-numeric discord_id=%s (guild=%s, user_id=%s)",
							raw_key,
							guild.id,
							user.user_id,
						)
						continue
					users[key] = user

			if users:
				entry["users"] = users
				self.guild_data[guild.id] = entry
				return
			# Fallback: DB exists but users collection is empty; scrape members
			logging.info(
				"No users found in DB for %s; scraping members as fallback", guild.name
			)

		logging.info(f"Scraping {guild.name} ({guild.member_count} members)...")
		snapshot: list[discord.Member] = list(guild.members)
		users = {m.id: User.from_member(m) for m in snapshot if not m.bot}
		for user in users.values():
			user.guild_id = guild.id

		entry["users"] = users
		self.guild_data[guild.id] = entry

		docs = []
		for user in users.values():
			payload = to_bson(user)
			payload["guild_id"] = payload.get("guild_id") or guild.id
			docs.append(payload)

		if docs:
			await asyncio.to_thread(entry["db"].users.insert_many, docs)

		logging.info(
			"Initial cache and DB created for %s - %d users", guild.name, len(users)
		)


if __name__ == "__main__":

	logging.basicConfig(level=logging.INFO)

	log_dir = Path("/app/logs")
	try:
		log_dir.mkdir(parents=True, exist_ok=True)
	except Exception as exc:  # pragma: no cover - defensive logging
		logging.warning("Unable to create log directory %s: %s", log_dir, exc)
	else:
		file_handler = logging.FileHandler(log_dir / "bot.log", mode="w")
		file_handler.setLevel(logging.INFO)
		file_handler.setFormatter(
			logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
		)
		logging.getLogger().addHandler(file_handler)

	intents = discord.Intents.default()
	intents.message_content = True
	intents.reactions = True
	intents.members = True
	intents.voice_states = True

	asyncio.run(Nonagon(intents=intents).start(BOT_TOKEN))
