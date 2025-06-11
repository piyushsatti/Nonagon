import logging
import discord
from discord.ext import commands

from ..models import UserModel

class GuildJoinCog(commands.Cog):
  """Handles telemetry when user joins guild.
  """

  def __init__(self, bot: commands.Bot):
    self.bot = bot
    logging.info("GuildJoinCog initialized")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
      
      logging.info(f"Member {member} joined the guild {member.guild.name}")
      
      # how do i now save this new user to DB?
      user = UserModel(
        _id=member.id,
        joined_at=member.joined_at,
        last_active_at=member.joined_at,
        messages_count_total=0,
        messages_count_by_category={},
        reactions_given=0,
        reactions_received=0,
        count_draw_steel_mentioned=0,
        voice_total_time_spent=0,
        voice_time_spent_in_hangout=0,
        voice_time_spent_in_game=0,
        events_attended=0,
        events_organized=0
      )
    
def setup(bot: commands.Bot):
  bot.add_cog(GuildJoinCog(bot))
  logging.info("GuildJoinCog loaded")