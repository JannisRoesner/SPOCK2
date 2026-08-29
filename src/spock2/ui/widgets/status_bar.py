"""Statusleiste: RIKER/PICARD/Drucker/letzter Erfolg."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics, QResizeEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from spock2.domain.status import ApiStatus, AppStatus, ConnectionState, PrinterStatus
from spock2.ui.assets import logo_pixmap

# Fehlerklasse → kurze, lesbare Anzeige. Der Rohtext (OpenSSL, httpx) ist in
# einer Kiosk-Statusleiste unlesbar und wurde bisher mitten im Wort abgeschnitten.
_ERROR_KIND_LABELS: dict[str, str] = {
    "TlsError": "Zertifikatsfehler",
    "TimeoutError": "Zeitüberschreitung",
    "NetworkError": "nicht erreichbar",
    "HttpStatusError": "HTTP-Fehler",
    "ValidationError": "Antwort ungültig",
    "AuthError": "Anmeldung abgelehnt",
}


def _fmt_time(value: datetime | None) -> str:
    if value is None:
        return "—"
    local = value.astimezone() if value.tzinfo else value
    return local.strftime("%H:%M:%S")


def short_error(status: ApiStatus) -> str:
    """Kurzform des Fehlers für die Statusleiste."""
    if status.error_kind and status.error_kind in _ERROR_KIND_LABELS:
        return _ERROR_KIND_LABELS[status.error_kind]
    err = (status.last_error or "").strip()
    if not err:
        return "offline"
    return err if len(err) <= 28 else err[:27] + "…"


def _api_label(name: str, status: ApiStatus) -> tuple[str, str]:
    """(text, objectName)."""
    if status.state == ConnectionState.CONNECTED:
        return (f"{name}: online", "statusOk")
    if status.state == ConnectionState.CONNECTING:
        return (f"{name}: verbindet…", "statusWarn")
    return (f"{name}: {short_error(status)}", "statusErr")


def _printer_label(statuses: list[PrinterStatus]) -> tuple[str, str]:
    if not statuses:
        return ("Drucker: —", "statusLabel")
    bad = [s for s in statuses if not (s.online and s.accepting_jobs)]
    if not bad:
        return ("Drucker: bereit", "statusOk")
    names = ", ".join(s.role for s in bad)
    reason = next((s.last_error for s in bad if s.last_error), "")
    text = f"Drucker {names}: {reason}" if reason else f"Drucker: Problem ({names})"
    return (text, "statusErr")


class ElidedLabel(QLabel):
    """QLabel, das zu langen Text kürzt statt ihn abzuschneiden."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.set_full_text(text)

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._apply_elide()

    def full_text(self) -> str:
        return self._full_text

    def minimumSizeHint(self) -> QSize:  # noqa: N802 – Qt-API
        hint = super().minimumSizeHint()
        return QSize(min(48, hint.width()), hint.height())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        metrics = QFontMetrics(self.font())
        available = self.width() - 4
        if available <= 16:
            super().setText(self._full_text)
            return
        super().setText(
            metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, available)
        )


class StatusBarWidget(QFrame):
    """Untere Statusleiste für Kiosk-Betrieb."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        self._logo = QLabel()
        self._logo.setObjectName("statusLogo")
        self._logo.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        brand = logo_pixmap(small=True, height=24)
        if not brand.isNull():
            self._logo.setPixmap(brand)
            self._logo.setFixedHeight(28)
            layout.addWidget(self._logo)

        # Nur die Statusmeldungen dürfen gekürzt werden; die kurzen Zähler
        # behalten ihre volle Breite, damit nichts mitten im Wort abbricht.
        self._riker = ElidedLabel("RIKER: —")
        self._picard = ElidedLabel("PICARD: —")
        self._printer = ElidedLabel("Drucker: —")
        self._last = QLabel("Abruf: —")
        self._orders = QLabel("Offen: 0")
        self._queue = QLabel("Queue: 0")
        self._failed = QLabel("")
        self._failed.setObjectName("statusErr")
        self._failed.setVisible(False)

        for label, stretch in (
            (self._riker, 2),
            (self._picard, 2),
            (self._printer, 3),
            (self._last, 0),
            (self._orders, 0),
            (self._queue, 0),
            (self._failed, 0),
        ):
            if label.objectName() == "":
                label.setObjectName("statusLabel")
            label.setAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
            layout.addWidget(label, stretch)

    def update_from_app_status(self, status: AppStatus | Any) -> None:
        if not isinstance(status, AppStatus):
            return
        self._set_api(self._riker, "RIKER", status.riker_status)
        self._set_api(self._picard, "PICARD", status.picard_status)
        self.update_printers(list(status.printer_statuses))

        self._last.setText(f"Abruf: {_fmt_time(status.orders_cache_updated_at)}")
        self._orders.setText(f"Offen: {status.orders_cached}")
        self._queue.setText(f"Queue: {status.pending_print_jobs}")

    def update_riker(self, status: ApiStatus) -> None:
        self._set_api(self._riker, "RIKER", status)
        if status.last_success_at is not None:
            self._last.setText(f"Abruf: {_fmt_time(status.last_success_at)}")

    def update_picard(self, status: ApiStatus) -> None:
        self._set_api(self._picard, "PICARD", status)

    def update_printers(self, statuses: list[PrinterStatus]) -> None:
        text, name = _printer_label(statuses)
        self._printer.set_full_text(text)
        self._restyle(self._printer, name)

    def update_order_count(self, count: int) -> None:
        self._orders.setText(f"Offen: {count}")

    def update_pending_jobs(self, count: int) -> None:
        self._queue.setText(f"Queue: {count}")

    def update_failed_jobs(self, count: int) -> None:
        self._failed.setVisible(count > 0)
        self._failed.setText(f"Druckfehler: {count}" if count else "")

    def _set_api(self, label: ElidedLabel, name: str, status: ApiStatus) -> None:
        text, obj = _api_label(name, status)
        label.set_full_text(text)
        if status.state == ConnectionState.OFFLINE and status.last_error:
            label.setToolTip(f"{name}: {status.last_error}")
        self._restyle(label, obj)

    @staticmethod
    def _restyle(label: QLabel, object_name: str) -> None:
        if label.objectName() == object_name:
            return
        label.setObjectName(object_name)
        label.style().unpolish(label)
        label.style().polish(label)
