import logging

from discord.ext import commands
from discord.app_commands import CommandTree
from discord import Interaction

class DMHandlerCog(commands.Cog):

  def __init__(self, bot):
    self.bot = bot

  @CommandTree.command(name="register", description="Register a new user")
  async def register(self, interaction: Interaction):
    await interaction.response.send_message("Registration command invoked!")

def setup(bot):
  bot.add_cog(DMHandlerCog(bot))