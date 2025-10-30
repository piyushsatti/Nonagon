"""Shared logging helpers for the Discord bot.

This module centralizes logger creation so each module can simply call
``get_logger(__name__)`` and receive a logger with Nonagon defaults. The
logger exposes helpers for the two major logging paths we care about:

* **Structured logs** for internal observability.
* **Demo logs** which are user-facing audit trail entries posted to guild
  channels.

Business logic should rely on these helpers so that message formatting stays
consistent and the distinction between structured vs. demo logging remains in
one place.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, cast

DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
"""Default format applied to bot loggers."""

DEFAULT_LEVEL = logging.INFO
"""Default logging level for bot loggers."""

_LOGGER_CLASS_CONFIGURED = False
_LOGGING_CONFIGURED = False


def _ensure_logging_configured() -> None:
    """Apply Nonagon defaults the first time logging is requested."""

    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return
    logging.basicConfig(level=DEFAULT_LEVEL, format=DEFAULT_FORMAT)
    _LOGGING_CONFIGURED = True


class BotLogger(logging.Logger):
    """Logger with helpers for structured and demo logging."""

    def structured(self, event: str, **fields: Any) -> None:
        """Emit a structured log entry.

        Parameters
        ----------
        event:
            Identifier for the event being logged.
        **fields:
            Additional context to attach to the entry.
        """

        if fields:
            self.info("event=%s %s", event, fields)
        else:
            self.info("event=%s", event)

    async def audit(
        self,
        bot: Any,
        guild: Any,
        message: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Send a demo log message and record a structured audit entry.

        Demo logs are user-facing audit records posted in the configured guild
        channel. They should accompany successful state changes where moderators
        need an immutable trail. Structured logs, by contrast, remain internal
        diagnostics. This helper ensures both pathways stay in sync without the
        caller needing to choose explicitly.
        """

        formatted = _format_message(message, args, kwargs)
        # Import lazily to avoid circular imports during module initialization.
        from app.bot.utils.log_stream import send_demo_log

        await send_demo_log(bot, guild, formatted)
        guild_id = getattr(guild, "id", None)
        self.structured("demo_log", guild_id=guild_id, message=formatted)


def _ensure_logger_class() -> None:
    """Make sure ``logging`` constructs ``BotLogger`` instances."""

    global _LOGGER_CLASS_CONFIGURED
    if _LOGGER_CLASS_CONFIGURED:
        return
    logging.setLoggerClass(BotLogger)
    _LOGGER_CLASS_CONFIGURED = True


def get_logger(name: str) -> BotLogger:
    """Return a module-scoped :class:`BotLogger` with default configuration."""

    _ensure_logger_class()
    _ensure_logging_configured()
    logger = logging.getLogger(name)
    if not isinstance(logger, BotLogger):
        # Upgrade previously-created standard loggers in-place.
        logger.__class__ = BotLogger
    return cast(BotLogger, logger)


def _format_message(
    template: str, args: tuple[Any, ...], kwargs: Mapping[str, Any]
) -> str:
    if args and kwargs:
        raise ValueError("Provide either args or kwargs when formatting demo logs.")
    if kwargs:
        return template % dict(kwargs)
    if args:
        return template % args
    return template


__all__ = ["BotLogger", "DEFAULT_FORMAT", "get_logger"]
