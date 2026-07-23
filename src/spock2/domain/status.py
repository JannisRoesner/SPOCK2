"""Verbindungs- und Anwendungsstatus."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ConnectionState(StrEnum):
    CONNECTED = "connected"
    CONNECTING = "connecting"
    OFFLINE = "offline"


class ApiStatus(BaseModel):
    """Status einer Backend-API (RIKER/PICARD)."""

    state: ConnectionState = ConnectionState.OFFLINE
    last_success_at: datetime | None = None
    last_error: str | None = None
    error_kind: str | None = None

    def mark_success(self) -> None:
        self.state = ConnectionState.CONNECTED
        self.last_success_at = datetime.now(UTC)
        self.last_error = None
        self.error_kind = None

    def mark_error(self, message: str, *, kind: str | None = None) -> None:
        self.state = ConnectionState.OFFLINE
        self.last_error = message
        self.error_kind = kind

    def mark_connecting(self) -> None:
        self.state = ConnectionState.CONNECTING


class PrinterStatus(BaseModel):
    """Status einer CUPS-Rollenqueue."""

    role: str
    queue_name: str
    online: bool = False
    accepting_jobs: bool = False
    last_error: str | None = None
    last_checked_at: datetime | None = None

    def mark_checked(
        self,
        *,
        online: bool,
        accepting_jobs: bool,
        error: str | None = None,
    ) -> None:
        self.online = online
        self.accepting_jobs = accepting_jobs
        self.last_error = error
        self.last_checked_at = datetime.now(UTC)


class AppStatus(BaseModel):
    """Aggregierter App-Status für Statusleiste / Monitor."""

    orders_cached: int = 0
    orders_cache_updated_at: datetime | None = None
    riker_status: ApiStatus = Field(default_factory=ApiStatus)
    picard_status: ApiStatus = Field(default_factory=ApiStatus)
    printer_statuses: list[PrinterStatus] = Field(default_factory=list)
    pending_print_jobs: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
