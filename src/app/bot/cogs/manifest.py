"""Explicit list of bot extensions loaded when AUTO_LOAD_COGS is enabled."""

DEFAULT_EXTENSIONS: tuple[str, ...] = (
    "app.bot.cogs.admin.extension_manager",
    "app.bot.cogs.admin.permissions",
    "app.bot.cogs.admin.diagnostics",
    "app.bot.cogs.listeners.guild_listeners",
    "app.bot.cogs.character.cog",
    "app.bot.cogs.guild.cog",
    "app.bot.cogs.help.cog",
    "app.bot.cogs.lookup.cog",
    "app.bot.cogs.setup.cog",
    "app.bot.cogs.stats.cog",
    "app.bot.cogs.summary.cog",
    "app.bot.cogs.quests.cog",
)


__all__ = ["DEFAULT_EXTENSIONS"]
