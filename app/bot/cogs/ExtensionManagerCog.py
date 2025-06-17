import importlib
import logging
from discord.ext import commands

class ExtensionManagerCog(commands.Cog):

  def __init__(self, bot: commands.Bot):
    self.bot = bot

  async def on_command_error(self, ctx: commands.Context, error: Exception):
    
    if isinstance(error, commands.CommandNotFound):
      return
    
    traceback = logging.Formatter().formatException(error.__traceback__)
    if isinstance(error, commands.CheckFailure):
      logging.error(f"Check failed for command {ctx.command}:\n{traceback}")
    elif isinstance(error, commands.CommandInvokeError):
      logging.error(f"Error invoking command {ctx.command}:\n{traceback}")
    elif isinstance(error, commands.ExtensionNotFound):
      logging.error(f"Extension {ctx.command} not found:\n{traceback}")
    elif isinstance(error, commands.ExtensionAlreadyLoaded):
      logging.error(f"Extension {ctx.command} is already loaded:\n{traceback}")
    elif isinstance(error, commands.ExtensionFailed):
      logging.error(f"Failed to load extension {ctx.command}:\n{traceback}")
    else:
      logging.error(f"Error in command {ctx.command}:\n{traceback}")

    await ctx.send(f"An error occurred while processing the command: `{error}`")

  async def cog_before_invoke(self, ctx):
    logging.info(f"Command invoked: {ctx.command} by {ctx.author} in {ctx.guild}")
    return await super().cog_before_invoke(ctx)
  
  async def cog_after_invoke(self, ctx):
    logging.info(f"Command completed: {ctx.command} by {ctx.author} in {ctx.guild}")
    return await super().cog_after_invoke(ctx)

  @commands.is_owner()
  @commands.command(name="load")
  async def load_extension(self, ctx: commands.Context, ext: str):
    self.bot.load_extension(ext)

  @commands.is_owner()
  @commands.command(name="unload")
  async def unload_extension(self, ctx: commands.Context, ext: str):
    self.bot.unload_extension(ext)

  @commands.is_owner()
  @commands.command(name="reload")
  async def reload_extension(self, ctx: commands.Context, ext: str):
    importlib.reload(importlib.import_module(ext))
    self.bot.reload_extension(ext)

  @commands.is_owner()
  @commands.command(name="extensions")
  async def list_extensions(self, ctx: commands.Context):

    if not self.bot.extensions:
      logging.info("No extensions loaded.")
      await ctx.send("No extensions loaded.")
      return
    
    exts = "\n".join(self.bot.extensions.keys()) or "(none)"
    logging.info(f"Loaded extensions: {exts}")
    await ctx.send(f"Loaded extensions:\n{exts}")

async def setup(bot: commands.Bot):
  await bot.add_cog(ExtensionManagerCog(bot))