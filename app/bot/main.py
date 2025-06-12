from datetime import datetime
import logging, asyncio

import discord
from discord.ext import commands

from .config import BOT_TOKEN, LEVEL_ANNOUNCE_CHANNEL, SUMMARY_CHANNEL, INACTIVITY_DAYS
from .database import db
from .cogs.ListnerCog import ListnerCog
from .models.UserModel import User

class Nonagon:
  """Main bot class that initializes the Discord bot and loads cogs.
  This class is responsible for setting up the bot, registering events,
  and loading the necessary cogs for functionality.
  """

  def __init__(self):
    self.intents = discord.Intents.default()
    self.intents.message_content = True
    self.intents.reactions       = True
    self.intents.members         = True 
    self.intents.voice_states    = True 

    self.bot = commands.Bot(command_prefix="!", intents=self.intents)
    self._register_events()

    self.bot.config = {
      "level_announce_channel": LEVEL_ANNOUNCE_CHANNEL,
      "summary_channel": SUMMARY_CHANNEL,
      "inactivity_days": INACTIVITY_DAYS,
    }

    self.bot.db = db

    self.bot.guild_data = {
      "users": {},
      "players": {},
      "characters": {},
      "referees": {},
    }
  
  def _register_events(self):
    @self.bot.event
    async def on_ready():
      logging.info(f"""
        ------------- Bot Ready ------------
        Logged in as {self.bot.user} (ID: {self.bot.user.id})
        ------------- Bot Info -------------
        Loaded Cogs: {list(self.bot.cogs)}
        ------------- Bot Commands ---------
        Valid Commands: {[c.name for c in self.bot.commands]}
      """)

      guild = self.bot.guilds[0]             # pick the first / only guild
      added = 0
      for member in guild.members:
        if member.bot:
          continue                           # ignore bots
        if member.id in self.bot.guild_data["users"]:
          continue                           # already seeded by on_member_join
        self.bot.guild_data["users"][member.id] = User(
          user_id        = member.id,
          joined_at      = member.joined_at or datetime.now(),
          last_active_at = datetime.now()
        )
        added += 1

      logging.info(
        f"Seeded {added} existing members into guild_data; "
        f"total users = {len(self.bot.guild_data['users'])}"
      )
      
  async def start(self):
    logging.info("Starting loading extensions...")

    try:
      for ext in (
        "app.bot.cogs.ListnerCog",
      ):
        
        logging.info(f"{ListnerCog.__name__}: Initializing...")
        await self.bot.add_cog(ListnerCog(self.bot))
        logging.info(f"{ListnerCog.__name__}: Initialized successfully.")

    except Exception as e:
      logging.error(f"Failed to load extension {ext}: {e}")
      raise e

    logging.info("All extensions loaded successfully.")
    await self.bot.start(BOT_TOKEN)

  def run(self):
    asyncio.run(self.start())
        
if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO)
  Nonagon().run()