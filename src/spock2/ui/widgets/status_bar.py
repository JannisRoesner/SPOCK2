"""Statusleiste: RIKER/PICARD/Drucker/letzter Erfolg."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from spock2.domain.status import ApiStatus, AppStatus, ConnectionState, PrinterStatus


def _fmt_time(value: datetime | None) -> str:
    if value is None:
        return "—"
    local = value.astimezone() if value.tzinfo else value
    return local.strftime("%H:%M:%S")


def _api_label(name: str, status: ApiStatus) -> tuple[str, str]:
    """(text, objectName)."""
    if status.state == ConnectionState.CONNECTED:
        return (f"{name}: online", "statusOk")
    if status.state == ConnectionState.CONNECTING:
        return (f"{name}: verbindet…", "statusWarn")
    err = status.last_error or "offline"
    short = err if len(err) <= 40 else err[:37] + "…"
    return (f"{name}: {short}", "statusErr")


def _printer_label(statuses: list[PrinterStatus]) -> tuple[str, str]:
    if not statuses:
        return ("Drucker: —", "statusLabel")
    bad = [s for s in statuses if not (s.online and s.accepting_jobs)]
    if not bad:
        return ("Drucker: bereit", "statusOk")
    names = ", ".join(s.role for s in bad)
    return (f"Drucker: Problem ({names})", "statusErr")


class StatusBarWidget(QFrame):
    """Untere Statusleiste für Kiosk-Betrieb."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        self._riker = QLabel("RIKER: —")
        self._riker.setObjectName("statusLabel")
        self._picard = QLabel("PICARD: —")
        self._picard.setObjectName("statusLabel")
        self._printer = QLabel("Drucker: —")
        self._printer.setObjectName("statusLabel")
        self._last = QLabel("Letzter Abruf: —")
        self._last.setObjectName("statusLabel")
        self._orders = QLabel("Bestellungen: 0")
        self._orders.setObjectName("statusLabel")
        self._queue = QLabel("Druckqueue: 0")
        self._queue.setObjectName("statusLabel")

        for label in (
            self._riker,
            self._picard,
            self._printer,
            self._last,
            self._orders,
            self._queue,
        ):
            label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(label)

        layout.addStretch(1)

    def update_from_app_status(self, status: AppStatus | Any) -> None:
        if not isinstance(status, AppStatus):
            return
        self._set_api(self._riker, "RIKER", status.riker_status)
        self._set_api(self._picard, "PICARD", status.picard_status)
        text, name = _printer_label(list(status.printer_statuses))
        self._printer.setText(text)
        self._printer.setObjectName(name)
        self._printer.style().unpolish(self._printer)
        self._printer.style().polish(self._printer)

        self._last.setText(f"Letzter Abruf: {_fmt_time(status.orders_cache_updated_at)}")
        self._orders.setText(f"Bestellungen: {status.orders_cached}")
        self._queue.setText(f"Druckqueue: {status.pending_print_jobs}")

    def update_riker(self, status: ApiStatus) -> None:
        self._set_api(self._riker, "RIKER", status)
        if status.last_success_at is not None:
            self._last.setText(f"Letzter Abruf: {_fmt_time(status.last_success_at)}")

    def update_picard(self, status: ApiStatus) -> None:
        self._set_api(self._picard, "PICARD", status)

    def update_printers(self, statuses: list[PrinterStatus]) -> None:
        text, name = _printer_label(statuses)
        self._printer.setText(text)
        self._printer.setObjectName(name)
        self._printer.style().unpolish(self._printer)
        self._printer.style().polish(self._printer)

    def update_order_count(self, count: int) -> None:
        self._orders.setText(f"Bestellungen: {count}")

    def update_pending_jobs(self, count: int) -> None:
        self._queue.setText(f"Druckqueue: {count}")

    def _set_api(self, label: QLabel, name: str, status: ApiStatus) -> None:
        text, obj = _api_label(name, status)
        label.setText(text)
        label.setObjectName(obj)
        label.style().unpolish(label)
        label.style().polish(label)
