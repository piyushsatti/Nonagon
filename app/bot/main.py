import logging, asyncio

import discord
from discord.ext import commands

from .config import BOT_TOKEN

class Nonagon:
  def __init__(self):
    self.intents = discord.Intents.default()
    self.intents.message_content = True
    self.intents.reactions       = True

    self.bot = commands.Bot(command_prefix="!", intents=self.intents)
    self._register_events()
  
  def _register_events(self):
    @self.bot.event
    async def on_ready():
      logging.info(f"✅ Logged in as {self.bot.user} (ID: {self.bot.user.id})")
      logging.info(f"🔌 Loaded Cogs: {list(self.bot.cogs)}")
      logging.info(f"📜 Commands: {[c.name for c in self.bot.commands]}")
      
  async def start(self):
    for ext in (
      "bot.cogs.quest",
      "bot.cogs.character",
      "bot.cogs.engagement",
      "bot.cogs.admin",
      "bot.cogs.automation",
    ):
      await self.bot.load_extension(ext)
      logging.info(f"✔ Loaded extension {ext}")

    await self.bot.start(BOT_TOKEN)

  def run(self):
    asyncio.run(self.start())
        
if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO)
  Nonagon().run()