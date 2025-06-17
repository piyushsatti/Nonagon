import logging

from ..app.bot.database import db_client
from ..app.bot.main import Nonagon

from discord.ext import commands
from discord import Guild

from ..app.bot.models.UserModel import User

class GuildListenerCog(commands.Cog):

  def __init__(self, bot: commands.Bot):
    self.bot: Nonagon = bot
  
  @commands.Cog.listener()
  async def on_guild_join(self, guild: Guild):
    """When joining a guild:
    - Scrape and create Users from Guild.Members
    - Create database for new guild
    - Save all data to cache"""

    logging.info(f"Joined new guild: {guild.name} (ID: {guild.id})")

    users = {}
    for member in guild.members:
      
      if member.bot:
        continue
      
      logging.info(f"Creating user cache for {member.name} (ID: {member.id})")
      users[member.id] = User.from_member(member)

      await self.bot.dirty_data.put((guild.id, member.id))


    db_name = f"{guild.id}"
    g_db = db_client.get_database(db_name)

    self.bot.guild_data[guild.id] = {
      "db": g_db,
      "users": users
    }
    logging.info(f"Cache created for guild {guild.name}.")

  @commands.Cog.listener()
  async def on_guild_remove(self, guild: Guild):
    logging.info(f"Left guild: {guild.name} (ID: {guild.id}) \nRemoving cache...")
    self.bot.guild_data.pop(guild.id, None)
    logging.info(f"Removed caches for guild {guild.name}.")

  @commands.Cog.listener()
  async def on_error(self, event_method, /, *args, **kwargs):
    logging.error(f"Error in {event_method}: {args} {kwargs}")
    await super().on_error(event_method, *args, **kwargs)

def setup(bot: commands.Bot):
  bot.add_cog(GuildListenerCog(bot))