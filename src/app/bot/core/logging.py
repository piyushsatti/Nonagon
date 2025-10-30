from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Serialize log records as structured JSON."""

    default_time_format = "%Y-%m-%dT%H:%M:%S"
    default_msec_format = "%s.%03dZ"

    def format(self, record: logging.LogRecord) -> str:
        data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.default_time_format),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            data["stack_info"] = record.stack_info
        return json.dumps(data, ensure_ascii=False)


def configure_logging() -> None:
    """Configure root logging handlers once for the bot runtime."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir_env = os.getenv("LOG_DIR")
    log_dir = Path(log_dir_env) if log_dir_env else Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_format = os.getenv("LOG_FORMAT", "").strip().lower()
    use_json = log_format == "json"

    log_file = log_dir / "bot.log"
    try:
        log_file.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        # best-effort; proceed even if we cannot truncate
        pass

    handlers: list[logging.Handler] = []

    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    stream_handler = logging.StreamHandler()

    if use_json:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    handlers.extend([file_handler, stream_handler])

    logging.basicConfig(
        level=logging.INFO,
        handlers=handlers,
        force=True,
    )

    _CONFIGURED = True


__all__ = ["configure_logging"]
