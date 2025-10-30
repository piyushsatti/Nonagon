"""Explicit list of bot extensions loaded when AUTO_LOAD_COGS is enabled."""

DEFAULT_EXTENSIONS: tuple[str, ...] = (
    "app.bot.cogs.admin.extension_manager",
    "app.bot.cogs.admin.permissions",
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

# Short alias map for interactive commands (short -> full module path)
# Keep this list authoritative and deterministic for the extension manager.
ALIASES: dict[str, str] = {
    "extension_manager": "app.bot.cogs.admin.extension_manager",
    "permissions": "app.bot.cogs.admin.permissions",
    "listeners": "app.bot.cogs.listeners.guild_listeners",
    "character": "app.bot.cogs.character.cog",
    "guild": "app.bot.cogs.guild.cog",
    "help": "app.bot.cogs.help.cog",
    "lookup": "app.bot.cogs.lookup.cog",
    "setup": "app.bot.cogs.setup.cog",
    "stats": "app.bot.cogs.stats.cog",
    "summary": "app.bot.cogs.summary.cog",
    "quests": "app.bot.cogs.quests.cog",
}

__all__.extend(["ALIASES"])
