"""Pydantic-Modelle für die SPOCK2-TOML-Konfiguration."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

StationRole = Literal["kitchen", "counter"]
PrinterRoleName = Literal["kitchen", "counter", "small"]
LogFormat = Literal["keyvalue", "json"]
PrintTransportMode = Literal["auto", "cups", "winspool", "file"]
UiTheme = Literal["light", "dark"]


class RikerConfig(BaseModel):
    base_url: str = "http://127.0.0.1:3000"
    connect_timeout_s: float = 3.0
    read_timeout_s: float = 10.0
    complete_retries: int = Field(default=2, ge=0)


class PicardConfig(BaseModel):
    enabled: bool = True
    base_url: str = "http://127.0.0.1:5000"
    connect_timeout_s: float = 3.0
    read_timeout_s: float = 10.0
    session_id: str = ""
    kitchen_note_types: list[str] = Field(
        default_factory=lambda: ["anKueche", "anKüche", "kueche", "küche", "anAlle"]
    )


class TlsConfig(BaseModel):
    ssl_verify: bool = True
    ca_bundle: str = ""


class TimeoutsConfig(BaseModel):
    connect_timeout_s: float = 3.0
    read_timeout_s: float = 10.0
    cups_job_timeout_s: float = 120.0


class PollingConfig(BaseModel):
    """Poll-Intervalle. ``interval_s`` bleibt als Legacy-Alias (→ beide APIs)."""

    interval_s: float = Field(default=3.0, gt=0)
    riker_interval_s: float = Field(default=3.0, gt=0)
    picard_interval_s: float = Field(default=3.0, gt=0)
    single_flight: bool = True

    @model_validator(mode="before")
    @classmethod
    def _legacy_shared_interval(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = dict(data)
        legacy = raw.get("interval_s", 3.0)
        if "riker_interval_s" not in raw:
            raw["riker_interval_s"] = legacy
        if "picard_interval_s" not in raw:
            raw["picard_interval_s"] = legacy
        return raw

    @model_validator(mode="after")
    def _sync_legacy_interval(self) -> PollingConfig:
        # Legacy-Feld spiegelt RIKER-Intervall (für ältere Leser / Anzeige).
        object.__setattr__(self, "interval_s", self.riker_interval_s)
        return self


class BackoffConfig(BaseModel):
    initial_s: float = Field(default=3.0, gt=0)
    factor: float = Field(default=2.0, ge=1.0)
    max_s: float = Field(default=30.0, gt=0)
    reset_on_success: bool = True


class PrinterConfig(BaseModel):
    """Druckerrolle → logischer Queue-/Druckername + Profil."""

    model_config = ConfigDict(populate_by_name=True)

    role: PrinterRoleName
    queue: str = Field(
        validation_alias=AliasChoices("queue", "cups_queue"),
        serialization_alias="queue",
    )
    profile: str
    enabled: bool = True


class ProfileConfig(BaseModel):
    name: str
    paper_width_mm: int = Field(ge=1)
    dots_per_line: int = Field(ge=1)
    supports_cutter: bool = False
    encoding: str = "cp437"
    qr_as_bitmap: bool = False
    capabilities: list[str] = Field(default_factory=list)


class RoutingConfig(BaseModel):
    station_role: StationRole = "kitchen"
    category_routing: dict[str, list[PrinterRoleName]] = Field(default_factory=dict)

    @field_validator("category_routing", mode="before")
    @classmethod
    def _coerce_roles(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        out: dict[str, list[str]] = {}
        for key, roles in value.items():
            if isinstance(roles, str):
                out[str(key)] = [roles]
            else:
                out[str(key)] = list(roles)
        return out


class PrintConfig(BaseModel):
    auto_print_new_orders: bool = True
    auto_print_new_notes: bool = True
    auto_complete_after_print: bool = False
    transport: PrintTransportMode = "auto"
    default_copies: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=5, ge=1)
    retry_delay_s: float = Field(default=5.0, ge=0)


class UiConfig(BaseModel):
    fullscreen: bool = True
    confirm_complete: bool = True
    admin_pin: str = ""
    min_touch_target_px: int = Field(default=56, ge=32)
    theme: UiTheme = "light"
    ui_scale: float = Field(default=1.0, ge=0.75, le=1.75)
    scale_with_window: bool = True


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file_path: str = ""
    max_bytes: int = Field(default=5_242_880, ge=1024)
    backup_count: int = Field(default=5, ge=0)
    format: LogFormat = "keyvalue"

    def resolved_file_path(self) -> Path | None:
        if self.file_path:
            return Path(self.file_path).expanduser()
        return default_state_dir() / "spock2.log"


class DbConfig(BaseModel):
    path: str = ""

    def resolved_path(self) -> Path:
        if self.path:
            return Path(self.path).expanduser()
        return default_state_dir() / "spock2.db"


class DiagnosticsConfig(BaseModel):
    verbose: bool = False
    probe_usb_on_startup: bool = False


class AppConfig(BaseModel):
    """Vollständige Anwendungs-Konfiguration."""

    riker: RikerConfig = Field(default_factory=RikerConfig)
    picard: PicardConfig = Field(default_factory=PicardConfig)
    tls: TlsConfig = Field(default_factory=TlsConfig)
    timeouts: TimeoutsConfig = Field(default_factory=TimeoutsConfig)
    polling: PollingConfig = Field(default_factory=PollingConfig)
    backoff: BackoffConfig = Field(default_factory=BackoffConfig)
    printers: dict[str, PrinterConfig] = Field(default_factory=dict)
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    print: PrintConfig = Field(default_factory=PrintConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    db: DbConfig = Field(default_factory=DbConfig)
    diagnostics: DiagnosticsConfig = Field(default_factory=DiagnosticsConfig)

    def printer_for_role(self, role: PrinterRoleName) -> PrinterConfig | None:
        for printer in self.printers.values():
            if printer.role == role and printer.enabled:
                return printer
        return None


def apply_config_inplace(target: AppConfig, source: AppConfig) -> AppConfig:
    """Übernimmt **alle** Abschnitte aus ``source`` in ``target``.

    Die Objekt-Identität von ``target`` bleibt erhalten, weil Orchestrator und
    Worker dieselbe Referenz halten. Die Übernahme läuft generisch über
    ``model_fields``: so kann kein Abschnitt (z. B. ``tls``) vergessen werden,
    wenn die Config wächst.
    """
    updated = source.model_copy(deep=True)
    for name in AppConfig.model_fields:
        setattr(target, name, getattr(updated, name))
    return target


def default_state_dir() -> Path:
    """Standard-Zustandspfad (Windows: %LOCALAPPDATA%/spock2, sonst ~/.local/state/spock2)."""
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "spock2"
    return Path.home() / ".local" / "state" / "spock2"
