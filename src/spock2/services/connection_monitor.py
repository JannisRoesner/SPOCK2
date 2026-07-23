"""Aggregiert RIKER-/PICARD-ApiStatus und Druckerzustände zu AppStatus."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from PySide6.QtCore import QObject, Signal, Slot

from spock2.domain.status import ApiStatus, AppStatus, PrinterStatus

logger = logging.getLogger(__name__)


class ConnectionMonitor(QObject):
    """Sammelt Verbindungs- und Cache-Metadaten für die Statusleiste."""

    status_changed = Signal(object)  # AppStatus

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._status = AppStatus()

    @property
    def status(self) -> AppStatus:
        return self._status.model_copy(deep=True)

    def _emit(self) -> None:
        self.status_changed.emit(self.status)

    @Slot(object)
    def set_riker_status(self, status: object) -> None:
        if isinstance(status, ApiStatus):
            self._status.riker_status = status.model_copy(deep=True)
        elif isinstance(status, dict):
            self._status.riker_status = ApiStatus.model_validate(status)
        else:
            logger.warning("event=riker_status_bad_type type=%s", type(status))
            return
        self._emit()

    @Slot(object)
    def set_picard_status(self, status: object) -> None:
        if isinstance(status, ApiStatus):
            self._status.picard_status = status.model_copy(deep=True)
        elif isinstance(status, dict):
            self._status.picard_status = ApiStatus.model_validate(status)
        else:
            logger.warning("event=picard_status_bad_type type=%s", type(status))
            return
        self._emit()

    @Slot(int, object)
    def set_orders_cache(self, count: int, updated_at: object = None) -> None:
        self._status.orders_cached = int(count)
        if isinstance(updated_at, datetime):
            self._status.orders_cache_updated_at = updated_at
        elif updated_at is None:
            self._status.orders_cache_updated_at = datetime.now(UTC)
        self._emit()

    @Slot(object)
    def set_printer_statuses(self, statuses: object) -> None:
        if not isinstance(statuses, list):
            return
        parsed: list[PrinterStatus] = []
        for item in statuses:
            if isinstance(item, PrinterStatus):
                parsed.append(item)
            elif isinstance(item, dict):
                try:
                    parsed.append(PrinterStatus.model_validate(item))
                except Exception:  # noqa: BLE001
                    continue
        self._status.printer_statuses = parsed
        self._emit()

    @Slot(int)
    def set_pending_print_jobs(self, count: int) -> None:
        self._status.pending_print_jobs = int(count)
        self._emit()

    def snapshot(self) -> AppStatus:
        return self.status
