"""Drucker-/Queue-Gesundheit aus Transport-Status."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from spock2.domain.status import PrinterStatus

logger = logging.getLogger(__name__)


class PrinterHealth(QObject):
    """Trackt Online/Accepting-Status je Druckerrolle aus dem Transport."""

    statuses_changed = Signal(object)  # list[PrinterStatus]
    summary_changed = Signal(str)

    def __init__(
        self,
        *,
        role_queues: dict[str, str] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._role_queues: dict[str, str] = dict(role_queues or {})
        self._statuses: dict[str, PrinterStatus] = {}
        for role, queue in self._role_queues.items():
            self._statuses[role] = PrinterStatus(role=role, queue_name=queue)

    @property
    def statuses(self) -> list[PrinterStatus]:
        return [s.model_copy(deep=True) for s in self._statuses.values()]

    def configure_roles(self, role_queues: dict[str, str]) -> None:
        self._role_queues = dict(role_queues)
        for role, queue in self._role_queues.items():
            existing = self._statuses.get(role)
            if existing is None:
                self._statuses[role] = PrinterStatus(role=role, queue_name=queue)
            else:
                self._statuses[role] = existing.model_copy(update={"queue_name": queue})
        # Entferne Rollen die nicht mehr konfiguriert sind
        for role in list(self._statuses):
            if role not in self._role_queues:
                del self._statuses[role]
        self._emit()

    @Slot(object)
    def apply_transport_snapshot(self, snapshot: object) -> None:
        """Übernimmt Status vom CupsStatusWorker / Transport.

        Erwartet eine Liste von dicts oder PrinterStatus, oder ein Mapping
        ``{role|queue: {online, accepting_jobs, error}}``.
        """
        if isinstance(snapshot, list):
            for item in snapshot:
                self._apply_one(item)
        elif isinstance(snapshot, dict):
            for key, value in snapshot.items():
                if isinstance(value, PrinterStatus):
                    self._statuses[value.role] = value
                elif isinstance(value, dict):
                    role = str(value.get("role") or key)
                    queue = str(
                        value.get("queue_name")
                        or self._role_queues.get(role)
                        or key
                    )
                    status = self._statuses.get(role) or PrinterStatus(
                        role=role, queue_name=queue
                    )
                    status.mark_checked(
                        online=bool(value.get("online", False)),
                        accepting_jobs=bool(value.get("accepting_jobs", False)),
                        error=value.get("last_error") or value.get("error"),
                    )
                    self._statuses[role] = status
        self._emit()

    def mark_transport_unavailable(self, message: str = "Transport nicht verfügbar") -> None:
        for role, status in self._statuses.items():
            status.mark_checked(online=False, accepting_jobs=False, error=message)
            self._statuses[role] = status
        self._emit()

    def mark_all_ok(self) -> None:
        for role, status in self._statuses.items():
            status.mark_checked(online=True, accepting_jobs=True, error=None)
            self._statuses[role] = status
        self._emit()

    def refresh_from_transport(self, transport: Any) -> None:
        """Synchrone Abfrage – nur aus Worker-Threads aufrufen, nicht aus UI."""
        try:
            available = bool(transport.is_available())
        except Exception as exc:  # noqa: BLE001
            logger.warning("event=printer_health_available_failed err=%s", exc)
            self.mark_transport_unavailable(str(exc))
            return

        if not available:
            self.mark_transport_unavailable("Transport offline")
            return

        queues: list[str] = []
        try:
            queues = list(transport.list_queues() or [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("event=printer_health_list_failed err=%s", exc)
            self.mark_transport_unavailable(str(exc))
            return

        queue_set = {q.casefold() for q in queues}
        for role, queue_name in self._role_queues.items():
            online = queue_name.casefold() in queue_set or not queues
            # FileTransport: leere Liste kann „alles ok“ bedeuten
            if not queues and available:
                online = True
            status = self._statuses.get(role) or PrinterStatus(
                role=role, queue_name=queue_name
            )
            status.mark_checked(
                online=online,
                accepting_jobs=online,
                error=None if online else f"Queue fehlt: {queue_name}",
            )
            self._statuses[role] = status
        self._emit()

    def summary_text(self) -> str:
        if not self._statuses:
            return "Drucker: nicht konfiguriert"
        parts: list[str] = []
        for status in self._statuses.values():
            if status.online and status.accepting_jobs:
                parts.append(f"{status.role}=OK")
            elif status.online:
                parts.append(f"{status.role}=gestoppt")
            else:
                parts.append(f"{status.role}=offline")
        return "Drucker: " + ", ".join(parts)

    def _apply_one(self, item: object) -> None:
        if isinstance(item, PrinterStatus):
            self._statuses[item.role] = item
            return
        if isinstance(item, dict):
            try:
                status = PrinterStatus.model_validate(item)
            except Exception:  # noqa: BLE001
                return
            self._statuses[status.role] = status

    def _emit(self) -> None:
        # Touch last_checked wenn fehlend
        now = datetime.now(UTC)
        for status in self._statuses.values():
            if status.last_checked_at is None:
                status.last_checked_at = now
        self.statuses_changed.emit(self.statuses)
        self.summary_changed.emit(self.summary_text())
