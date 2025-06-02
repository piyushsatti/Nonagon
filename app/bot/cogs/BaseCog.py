import logging
import traceback
import discord
from discord.ext import commands

class BaseCog(commands.Cog):
  """
  Provides shared utilities:
   - Command invoke logging
   - Custom help command
   - Cog-level error handling
  """

  def __init__(self, bot: commands.Bot, admin_channel_id: int):
    self.bot = bot
    self.admin_channel_id = admin_channel_id

  @commands.Cog.listener()
  async def on_command(self, ctx: commands.Context):
    logging.info(f"Command invoked: {ctx.command} by {ctx.author}")

  async def cog_before_invoke(self, ctx: commands.Context):
    logging.debug(f"Starting: {ctx.command} (args={ctx.args}, kwargs={ctx.kwargs})")

  async def cog_after_invoke(self, ctx: commands.Context):
    logging.debug(f"Finished: {ctx.command}")

  def cog_check(self, ctx: commands.Context):
    if ctx.author.bot:
      raise commands.CheckFailure("Bots may not use commands.")
    return True

  async def cog_command_error(self, ctx: commands.Context, error: Exception):
    # Command param check: sends a user-friendly message
    if isinstance(error, commands.CheckFailure):
      return await ctx.send(f"Error: {error}")
    # Record Traceback
    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    logging.error(f"Error in {ctx.command}:\n{tb}")
    admin_ch = self.bot.get_channel(self.admin_channel_id)
    # Admin error notification
    if admin_ch:
      await admin_ch.send(f"⚠️ Error in `{ctx.command}` by {ctx.author}:\n```\n{tb}```")
    # User error notification
    await ctx.send("❌ An unexpected error occurred. Daddie has been notified.")

  @commands.command(name="help")
  async def custom_help(self, ctx: commands.Context):
    """
    Sends a help message grouping commands by cog.
    """
    embed = discord.Embed(
      title="Command Help",
      color=discord.Color.blurple()
    )
    for cog_name, cog in self.bot.cogs.items():
      commands_list = [
        f"**{cmd.name}**: {cmd.help or 'No description.'}"
        for cmd in cog.get_commands()
        if not cmd.hidden
      ]
      if commands_list:
        embed.add_field(
          name=cog_name,
          value="\n".join(commands_list),
          inline=False
        )
    await ctx.send(embed=embed)

def setup(bot: commands.Bot):
  bot.add_cog(
    BaseCog(
      bot, 
      admin_channel_id=1372610485353975903
  ))
