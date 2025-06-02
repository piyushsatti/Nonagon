# bot/cogs/player_cog.py
import re
import discord
from discord.ext import commands
from datetime import datetime
from ..database import players_col
from ..models.PlayerModel import Player
from ..models.CharacterModel import Character

class PlayerCog(commands.Cog):
  """Manage player profiles and characters."""

  def __init__(self, bot: commands.Bot):
    self.bot = bot
    print("PlayerCog loaded")

  # ──────── Helper ────────
  async def _get_or_create_player(self, user: discord.User) -> Player:
    # Find player in db
    doc = players_col.find_one({"user_id": str(user.id)})
    if doc:
      return Player(**doc)
    # Create new
    new_player = Player(
      user_id=str(user.id),
      user_name=str(user),
      joined_at=datetime.now(),
      last_active_at=datetime.now()
    )
    players_col.insert_one(new_player.__dict__)
    return new_player

  # ──────── Character Commands ────────
  @commands.group(name="character", invoke_without_command=True)
  async def character(self, ctx: commands.Context):
    await ctx.send("Usage: `!character add|view|delete`")

  @character.command(name="add")
  async def character_add(self, ctx: commands.Context, name: str, level: int = 1):
    if not re.match(r"^[A-Za-z0-9 _'-]{2,20}$", name):
      return await ctx.reply("Invalid name—use 2–20 alphanumerics/spaces.")
    player = await self._get_or_create_player(ctx.author)
    if any(c.name.lower() == name.lower() for c in player.active_characters):
      return await ctx.reply(f"You already have a character named **{name}**.")
    char = Character(
      character_id=str(ctx.author.id)+"_"+name,
      name=name,
      created_at=datetime.utcnow(),
      last_played_at=None,
      level=level
    )
    players_col.update_one(
      {"user_id": player.user_id},
      {"$push": {"active_characters": char.__dict__}}
    )
    await ctx.send(f"Character **{name}** (Lvl {level}) added to your roster.")

  @character.command(name="view")
  async def character_view(self, ctx: commands.Context):
    player = await self._get_or_create_player(ctx.author)
    if not player.active_characters:
      return await ctx.reply("You have no active characters.")
    lines = []
    for c in player.active_characters:
      last = c.last_played_at.isoformat() if c.last_played_at else "never"
      lines.append(f"• {c.name} (Lvl {c.level}, XP {c.xp}, last {last})")
    embed = discord.Embed(
      title=f"{ctx.author.name}'s Characters",
      description="\n".join(lines),
      color=discord.Color.green()
    )
    await ctx.send(embed=embed)

  @character.command(name="delete")
  async def character_delete(self, ctx: commands.Context, name: str):
    res = players_col.update_one(
      {"user_id": str(ctx.author.id)},
      {"$pull": {"active_characters": {"name": name}}}
    )
    if res.modified_count:
      await ctx.send(f"Character **{name}** removed.")
    else:
      await ctx.reply(f"No character named **{name}** found.")

  # ──────── Profile Command ────────
  @commands.command(name="myprofile")
  async def myprofile(self, ctx: commands.Context):
    player = await self._get_or_create_player(ctx.author)
    # Build embed
    embed = discord.Embed(
      title=f"{ctx.author.name}'s Profile",
      color=discord.Color.blue()
    )
    embed.add_field(
      name="Quests Played",
      value=str(player.total_quests),
      inline=True
    )
    embed.add_field(
      name="XP / GP",
      value=f"{player.total_xp} XP / {player.total_gp} GP",
      inline=True
    )
    embed.add_field(
      name="Messages / Reactions",
      value=(
        f"{player.messages_total} msgs\n"
        f"{player.reactions_given} given, {player.reactions_received} recvd"
      ),
      inline=False
    )
    # List characters
    if player.active_characters:
      chars = ", ".join(c.name for c in player.active_characters)
      embed.add_field(name="Characters", value=chars, inline=False)
    await ctx.send(embed=embed)

def setup(bot: commands.Bot):
  bot.add_cog(PlayerCog(bot))
