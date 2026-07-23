"""Strukturiertes Logging ohne Secrets."""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal

LogFormat = Literal["keyvalue", "json"]

# Schlüssel / Muster, die in Logausgaben maskiert werden
_SECRET_KEY_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization|admin_pin)\b"
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization|admin_pin)\s*[:=]\s*\S+"
)


class _RedactingFilter(logging.Filter):
    """Entfernt offensichtliche Secret-Werte aus Lognachrichten."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SECRET_VALUE_RE.sub(
                lambda m: f"{m.group(0).split('=')[0].split(':')[0]}=***",
                record.msg,
            )
        if record.args:
            # Args nicht tief umschreiben; Msg-Template reicht für Scaffold
            pass
        return True


class KeyValueFormatter(logging.Formatter):
    """Kompaktes key=value-Format mit UTC-Zeitstempel."""

    default_time_format = "%Y-%m-%dT%H:%M:%S"
    default_msec_format = "%s.%03dZ"

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        from datetime import UTC, datetime

        dt = datetime.fromtimestamp(record.created, tz=UTC)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z"

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record)
        msg = record.getMessage()
        base = (
            f"ts={ts} level={record.levelname} logger={record.name} "
            f"msg={_quote(msg)}"
        )
        if record.exc_info:
            base += f" exc={_quote(self.formatException(record.exc_info))}"
        return base


class JsonIshFormatter(logging.Formatter):
    """Einzeiliges JSON-ähnliches Format (ohne extra Dependency)."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        from datetime import UTC, datetime

        dt = datetime.fromtimestamp(record.created, tz=UTC)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z"

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict[str, str | int] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _quote(value: str) -> str:
    """Einfaches Quoting für Leerzeichen in key=value-Werten."""
    if re.search(r"[\s\"]", value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def setup_logging(
    *,
    level: str = "INFO",
    file_path: Path | str | None = None,
    max_bytes: int = 5_242_880,
    backup_count: int = 5,
    fmt: LogFormat = "keyvalue",
) -> None:
    """Konfiguriert Root-Logger mit Console + optionaler rotierender Datei."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = JsonIshFormatter() if fmt == "json" else KeyValueFormatter()

    redactor = _RedactingFilter()

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    console.addFilter(redactor)
    root.addHandler(console)

    if file_path:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redactor)
        root.addHandler(file_handler)

    # httpx/urllib3 etwas ruhiger halten
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def looks_like_secret_key(key: str) -> bool:
    """Hilfsfunktion: True, wenn der Schlüssel wie ein Secret aussieht."""
    return bool(_SECRET_KEY_RE.search(key))
