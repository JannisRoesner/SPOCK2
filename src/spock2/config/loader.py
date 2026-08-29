"""TOML-Konfiguration laden und speichern."""

from __future__ import annotations

import logging
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

from spock2.config.models import AppConfig

logger = logging.getLogger(__name__)

ENV_CONFIG = "SPOCK2_CONFIG"


def user_config_path() -> Path:
    """Benutzer-Config: ``%APPDATA%/spock2`` (Windows) bzw. ``~/.config/spock2``."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "spock2" / "spock2.toml"
    return Path.home() / ".config" / "spock2" / "spock2.toml"


def _default_search_paths() -> tuple[Path, ...]:
    """Suchreihenfolge: Projekt → Benutzer → System.

    Die Benutzer-Config gewinnt bewusst gegen ``/etc``, damit Start aus dem
    Startmenü, per systemd und aus der Shell dieselbe Datei benutzen.
    """
    paths: list[Path] = [
        Path("config/spock2.toml"),
        user_config_path(),
        Path("/etc/spock2/spock2.toml"),
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        appdata_path = Path(appdata) / "spock2" / "spock2.toml"
        if appdata_path not in paths:
            paths.append(appdata_path)
    return tuple(paths)


DEFAULT_WRITE_PATH = Path("config/spock2.toml")


@dataclass(frozen=True)
class LoadedConfig:
    """Geladene Config plus aufgelöster Dateipfad (None = nur Defaults)."""

    config: AppConfig
    path: Path | None


def resolve_config_path(override: str | Path | None = None) -> Path | None:
    """Ermittelt den Config-Pfad (Override → Env → bekannte Orte).

    Ein ``SPOCK2_CONFIG``, das auf eine fehlende Datei zeigt, ist **kein**
    harter Fehler: Kiosk-/Desktop-Starter setzen die Variable oft pauschal auf
    ``/etc/spock2/spock2.toml``. Statt beim Start abzubrechen (unsichtbar, wenn
    kein Terminal dranhängt) wird die normale Suche fortgesetzt.
    """
    if override is not None:
        path = Path(override).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Config nicht gefunden: {path}")
        return path

    env = os.environ.get(ENV_CONFIG)
    if env:
        path = Path(env).expanduser()
        if path.is_file():
            return path
        logger.warning(
            "event=config_env_missing var=%s path=%s – Suche wird fortgesetzt",
            ENV_CONFIG,
            path,
        )

    for candidate in _default_search_paths():
        expanded = candidate.expanduser()
        if expanded.is_file():
            return expanded
    return None


def default_writable_config_path() -> Path:
    """Standard-Schreibziel, wenn keine Config-Datei geladen wurde.

    Im Repo-/Dev-Layout (``config/`` existiert) bleibt es dabei; installiert
    wird in die Benutzer-Config geschrieben — nicht relativ zum
    Arbeitsverzeichnis, das beim Start aus dem Startmenü ``$HOME`` ist.
    """
    if DEFAULT_WRITE_PATH.parent.is_dir():
        return DEFAULT_WRITE_PATH
    return user_config_path()


def load_toml(path: Path) -> dict[str, Any]:
    """Liest eine TOML-Datei (stdlib tomllib, Python 3.12+)."""
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"TOML-Wurzel muss eine Tabelle sein: {path}")
    return data


def load_config_result(
    path: str | Path | None = None,
    *,
    allow_missing: bool = True,
) -> LoadedConfig:
    """Lädt TOML in ``AppConfig`` und liefert den Quellpfad mit."""
    resolved = resolve_config_path(path)
    if resolved is None:
        if allow_missing:
            return LoadedConfig(config=AppConfig(), path=None)
        raise FileNotFoundError(
            "Keine SPOCK2-Config gefunden. "
            f"Setze {ENV_CONFIG} oder lege config/spock2.toml an."
        )
    raw = load_toml(resolved)
    return LoadedConfig(config=AppConfig.model_validate(raw), path=resolved)


def load_config(
    path: str | Path | None = None,
    *,
    allow_missing: bool = True,
) -> AppConfig:
    """Lädt TOML in ``AppConfig``.

    Wenn keine Datei gefunden wird und ``allow_missing`` True ist,
    werden Defaults verwendet (nützlich für Tests/Scaffold).
    """
    return load_config_result(path, allow_missing=allow_missing).config


def _dump_ready(data: Any) -> Any:
    """Konvertiert model_dump-Ausgabe in tomli-w-freundliche Typen."""
    if isinstance(data, dict):
        return {str(k): _dump_ready(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_dump_ready(v) for v in data]
    if isinstance(data, Path):
        return str(data)
    return data


def save_config(path: str | Path, config: AppConfig) -> Path:
    """Schreibt ``AppConfig`` als TOML. Elternverzeichnis wird angelegt."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _dump_ready(config.model_dump(mode="python"))
    with target.open("wb") as fh:
        tomli_w.dump(payload, fh)
    return target
