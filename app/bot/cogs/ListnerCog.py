import logging
from datetime import datetime
from discord import Member, Message, RawReactionActionEvent, VoiceState, Guild
from discord.ext import commands

from ..database import db_client
from ..models.UserModel import User

class ListnerCog(commands.Cog):

  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self._voice_starts: dict[int, datetime] = {}
    self._voice_channels: dict[int, str] = {}

  @commands.Cog.listener("on_member_join")
  async def _on_member_join(self, member: Member):

    if member.bot:
      return

    self.bot.guild_data[member.guild.id]["users"][member.id] = User.from_member(member)
    await self.bot.dirty_data.put((member.guild.id, member.id))
    logging.info(f"User: {member.id} joined the guild. Joined At: {member.joined_at} Total Users: {len(self.bot.guild_data[member.guild.id]['users'])}")

  @commands.Cog.listener("on_message")
  async def on_message(self, message: Message):

    if message.author.bot:
      return

    logging.info(f"Message from {message.author.id} in {message.guild.id} at {message.created_at}: {message.content}")

    guild_id = message.guild.id
    author_id = message.author.id

    users = self.bot.guild_data.get(guild_id, {}).get("users", {})

    if author_id not in users:
      raise ValueError(f"User {author_id} not found in guild data for {guild_id}")

    user: User = users[author_id]
    user.messages_count_total += 1
    user.last_active_at = message.created_at

    category_id = str(message.channel.category.id)
    count = user.messages_count_by_category.get(category_id, 0)
    user.messages_count_by_category[category_id] = count + 1

    await self.bot.dirty_data.put((guild_id, author_id))
    logging.info(f"User: {user.user_id} sent a message. Channel: {message.channel.id} Category: {category_id} Total Messages: {user.messages_count_total} Messages by Category: {user.messages_count_by_category} Last Active At: {user.last_active_at}")

  @commands.Cog.listener("on_raw_reaction_add")
  async def _on_raw_reaction_add(self, reaction: RawReactionActionEvent):

    if reaction.member.bot:
      return
    
    if reaction.event_type != "REACTION_ADD":
      return
    
    if reaction.guild_id is None:
      logging.info(f"No guild ID in reaction: {reaction}")
      return
    
    guild_id = reaction.guild_id
    reacting_user_id = reaction.member.id
    message_author_id = reaction.message_author_id

    reacting_user = self.bot.guild_data[guild_id]["users"][reacting_user_id]
    author_user = self.bot.guild_data[guild_id]["users"][message_author_id]

    reacting_user.last_active_at = datetime.now()
    reacting_user.reactions_given += 1
    author_user.reactions_received += 1

    # count fun reactions
    if reaction.emoji.name is None and not reaction.emoji.is_custom_emoji():
      return

    if "ban" in reaction.emoji.name:
      author_user.fun_count_banned += 1
    elif "up" in reaction.emoji.name:
      author_user.fun_count_liked += 1
    elif "down" in reaction.emoji.name:
      author_user.fun_count_disliked += 1
    elif "kek" in reaction.emoji.name:
      author_user.fun_count_kek += 1
    elif "true" in reaction.emoji.name:
      author_user.fun_count_true += 1
    elif "heart" in reaction.emoji.name:
      author_user.fun_count_heart += 1

    await self.bot.dirty_data.put((guild_id, reacting_user_id))
    await self.bot.dirty_data.put((guild_id, message_author_id))
    logging.info(f"User: {reacting_user.user_id} reacted with {reaction.emoji.name} to message by {author_user.user_id} in channel {reaction.channel_id} Total Reactions Given: {reacting_user.reactions_given} Total Reactions Received: {author_user.reactions_received} Fun Reactions: {author_user.fun_count_banned}, {author_user.fun_count_liked}, {author_user.fun_count_disliked}, {author_user.fun_count_kek}, {author_user.fun_count_true}, {author_user.fun_count_heart}")

  @commands.Cog.listener("on_voice_state_update")
  async def _on_voice_state_update(
    self, 
    member: Member, 
    before: VoiceState, 
    after: VoiceState
  ):
    
    if member.bot:
      return

    if member.id not in self.bot.guild_data[member.guild.id]["users"]:
      return

    user = self.bot.guild_data[member.guild.id]["users"][member.id]
    user.last_active_at = datetime.now()
    start = None
    chan  = None
    
    if before.channel is None and after.channel is not None:
      
      self._voice_starts[member.id]   = datetime.now()
      self._voice_channels[member.id] = str(after.channel.id)

    elif before.channel is not None and after.channel is None:
      
      start = self._voice_starts.pop(member.id, None)
      chan  = self._voice_channels.pop(member.id, None)
      
      if start and chan:
        
        hours = (datetime.now() - start).total_seconds() / 3600
        user.voice_total_time_spent += hours

        if chan in user.voice_time_by_channel:
          user.voice_time_by_channel[chan] += hours
      
        else:
          user.voice_time_by_channel[chan] = hours

    elif before.channel is not None and after.channel is not None:
      
      start = self._voice_starts.get(member.id)
      chan  = self._voice_channels.get(member.id)
        
      # reset for new channel
      self._voice_starts[member.id]   = datetime.now()
      self._voice_channels[member.id] = str(after.channel.id)

    # before.channel is None and after.channel is None:
    else:
      
      logging.warning(f"""
        ------------- Cog Warning ------------
        Unexpected voice state update for user {member.id}
        with before: {before.channel} and after: {after.channel}
      """)
      return 
    
    if start and chan:
        
      hours = (datetime.now() - start).total_seconds() / 3600
      user.voice_total_time_spent += hours

      if chan in user.voice_time_by_channel:
        user.voice_time_by_channel[chan] += hours
    
      else:
        user.voice_time_by_channel[chan] = hours

    await self.bot.dirty_data.put((member.guild.id, member.id))
    logging.info(f"User: {user.user_id} changed voice state. Before: {before.channel} After: {after.channel} Total Voice Time: {user.voice_total_time_spent} hours Time by Channel: {user.voice_time_by_channel}")

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