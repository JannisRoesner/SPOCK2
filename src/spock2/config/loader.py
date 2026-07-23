"""TOML-Konfiguration laden."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from spock2.config.models import AppConfig

ENV_CONFIG = "SPOCK2_CONFIG"

_SEARCH_PATHS: tuple[Path, ...] = (
    Path("config/spock2.toml"),
    Path("/etc/spock2/spock2.toml"),
    Path.home() / ".config" / "spock2" / "spock2.toml",
)


def resolve_config_path(override: str | Path | None = None) -> Path | None:
    """Ermittelt den Config-Pfad (Override → Env → bekannte Orte)."""
    if override is not None:
        path = Path(override).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Config nicht gefunden: {path}")
        return path

    env = os.environ.get(ENV_CONFIG)
    if env:
        path = Path(env).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"{ENV_CONFIG} zeigt auf fehlende Datei: {path}")
        return path

    for candidate in _SEARCH_PATHS:
        expanded = candidate.expanduser()
        if expanded.is_file():
            return expanded
    return None


def load_toml(path: Path) -> dict[str, Any]:
    """Liest eine TOML-Datei (stdlib tomllib, Python 3.12+)."""
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"TOML-Wurzel muss eine Tabelle sein: {path}")
    return data


def load_config(
    path: str | Path | None = None,
    *,
    allow_missing: bool = True,
) -> AppConfig:
    """Lädt TOML in ``AppConfig``.

    Wenn keine Datei gefunden wird und ``allow_missing`` True ist,
    werden Defaults verwendet (nützlich für Tests/Scaffold).
    """
    resolved = resolve_config_path(path)
    if resolved is None:
        if allow_missing:
            return AppConfig()
        raise FileNotFoundError(
            "Keine SPOCK2-Config gefunden. "
            f"Setze {ENV_CONFIG} oder lege config/spock2.toml an."
        )
    raw = load_toml(resolved)
    return AppConfig.model_validate(raw)
