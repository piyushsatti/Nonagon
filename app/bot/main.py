import discord, logging, asyncio
from dataclasses import asdict
from pathlib import Path
from discord.ext import commands

from .config import BOT_TOKEN
from .models.UserModel import User
from .database import db_client

class Nonagon(commands.Bot):
  """Main bot class that initializes the Discord bot and loads cogs.
  This class is responsible for setting up the bot, registering events,
  and loading the necessary cogs for functionality.
  """

  def __init__(self, intents: discord.Intents):
    super().__init__(command_prefix="/", intents=intents)
    self.guild_data: dict[int, dict] = {}
    self.dirty_data: asyncio.Queue[tuple[int,int]] = asyncio.Queue()

  # Called before the bot logins to discord
  async def setup_hook(self):

    # Load every .py file under the bot/cogs directory as an extension
    cogs_path = Path(__file__).parent / "cogs"
    for file in cogs_path.glob("*.py"):
      if file.name.startswith("_"):
        continue                      # skip __init__.py and private modules
      ext = f"app.bot.cogs.{file.stem}"   # e.g. bot.cogs.my_cog
      try:
        await self.load_extension(ext)
      except Exception as e:
        traceback = logging.Formatter().formatException(e.__traceback__)
        logging.error(f"Error loading extension {ext}:\n{traceback}")
      else:
        logging.info(f"Loaded extension {ext}")

    try:
      self.loop.create_task(self._auto_persist_loop())
    except Exception as e:
      logging.error(f"Auto persist loop encountered an error: {e}")

    # Call the parent setup_hook to ensure all cogs are loaded
    await super().setup_hook()

  # Called to login and connect the bot to Discord
  async def start(self, BOT_TOKEN):
    await super().start(BOT_TOKEN)

  # Called when the bot is ready
  async def on_ready(self):    
    await self._load_cache()
    logging.info(f"Logged in as {self.user} (ID: {self.user.id}) \nLoaded Cogs: {list(self.cogs)} \nValid Commands: {[c.name for c in self.commands]}")

  async def on_error(self, event_method, /, *args, **kwargs):
    await super().on_error(event_method, *args, **kwargs)

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
      to_flush: dict[tuple[int,int], User] = {}
      try:
        while True:
          gid, uid = self.dirty_data.get_nowait()
          to_flush[(gid, uid)] = self.guild_data[gid]["users"][uid]
      except asyncio.QueueEmpty:
        pass
      
      for (gid, uid), user in to_flush.items():
        db = self.guild_data[gid]["db"]
        await asyncio.to_thread(
          db.users.update_one,           # ← callable
          {"user_id": uid},              # positional arg 1
          {"$set": asdict(user)},        # positional arg 2
          upsert=True                    # keyword arg
        )

  async def load_or_create_guild_cache(self, guild: discord.Guild) -> None:
    db_name = f"{guild.id}"

    if db_name in db_client.list_database_names():
      logging.info(f"Loading cached users for {guild.name}")
      g_db = db_client.get_database(db_name)
      docs = g_db.users.find({}, {"_id": 0})
      self.guild_data[guild.id] = {
        "db": g_db,
        "users": {doc["user_id"] : User.from_dict(doc) for doc in docs}
      }
      return

    logging.info(f"Scraping {guild.name} ({guild.member_count} members)...")
    snapshot: list[discord.Member] = list(guild.members)
    g_db = db_client.get_database(db_name)
    self.guild_data[guild.id] = {
      "db": g_db,
      "users" : { m.id: User.from_member(m) for m in snapshot if not m.bot }
    }

    db = self.guild_data[guild.id]["db"]
    users = self.guild_data[guild.id]["users"]

    docs = []
    for user in users.values():
      doc = asdict(user)
      doc["messages_count_by_category"] = {str(k): v for k, v in doc["messages_count_by_category"].items()}
      doc["voice_time_by_channel"] = {str(k): v for k, v in doc["voice_time_by_channel"].items()}
      docs.append(doc)

    await asyncio.to_thread(db.users.insert_many, docs)

    logging.info("Initial cache and DB created for %s - %d users", guild.name, len(users))

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO)

  intents = discord.Intents.default()
  intents.message_content = True
  intents.reactions       = True
  intents.members         = True 
  intents.voice_states    = True

  asyncio.run(
    Nonagon(intents=intents).start(BOT_TOKEN)
  )