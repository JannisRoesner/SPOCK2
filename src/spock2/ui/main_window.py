"""Hauptfenster: Order-Cards, Statusleiste, Menüs, Vollbild."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from spock2.config.models import AppConfig
from spock2.domain.notes import Note
from spock2.domain.orders import Order
from spock2.domain.status import ApiStatus, AppStatus, PrinterStatus
from spock2.printing.queue_discovery import list_system_queues
from spock2.services.connection_monitor import ConnectionMonitor
from spock2.services.note_service import NoteService
from spock2.services.order_service import OrderService
from spock2.ui.assets import app_icon, logo_pixmap
from spock2.ui.dialogs.admin_dialog import AdminDialog
from spock2.ui.dialogs.complete_confirm import CompleteConfirmDialog
from spock2.ui.dialogs.note_dialog import NoteDialog
from spock2.ui.dialogs.note_popup import NotePopup
from spock2.ui.theme import apply_appearance, load_stylesheet
from spock2.ui.widgets.order_card import OrderCard
from spock2.ui.widgets.status_bar import StatusBarWidget

logger = logging.getLogger(__name__)

SettingsApplyCallback = Callable[[AppConfig], str | None]
ConnectionTestCallback = Callable[[AppConfig], str]

__all__ = ["MainWindow", "load_stylesheet", "wanted_columns"]

# Zielbreite einer Bestellkarte; darüber wird mehrspaltig gelayoutet.
_CARD_TARGET_WIDTH = 380
_MAX_CARD_COLUMNS = 4


def wanted_columns(width: int) -> int:
    """Spaltenzahl für die Kartenfläche – mindestens 1, maximal ``_MAX_CARD_COLUMNS``."""
    return max(1, min(_MAX_CARD_COLUMNS, width // _CARD_TARGET_WIDTH))


class MainWindow(QMainWindow):
    """Küchen-Kiosk: scrollbare Order-Cards + Status."""

    def __init__(
        self,
        config: AppConfig,
        order_service: OrderService,
        *,
        note_service: NoteService | None = None,
        connection_monitor: ConnectionMonitor | None = None,
        orchestrator: Any | None = None,
        on_settings_apply: SettingsApplyCallback | None = None,
        on_connection_test: ConnectionTestCallback | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._orders = order_service
        self._notes = note_service
        self._monitor = connection_monitor
        self._orchestrator = orchestrator
        self._on_settings_apply = on_settings_apply
        self._on_connection_test = on_connection_test
        self._cards: dict[int, OrderCard] = {}
        self._card_order: list[int] = []
        self._columns = 0
        # Früh gesetzt: setMinimumSize() unten kann bereits ein resizeEvent auslösen.
        self._columns_widgets: list[QWidget] = []
        self._column_layouts: list[QVBoxLayout] = []
        self._offline = False
        self._tls_warned: set[str] = set()
        self._printer_warned: set[str] = set()
        self._open_note_popups: set[str] = set()
        self._appear_timer = QTimer(self)
        self._appear_timer.setSingleShot(True)
        self._appear_timer.timeout.connect(self.refresh_appearance)
        self._last_appear_size: tuple[int, int] | None = None
        self._banner_timer = QTimer(self)
        self._banner_timer.setSingleShot(True)
        self._banner_timer.timeout.connect(self._hide_banner)

        self.setWindowTitle("SPOCK2")
        self.setMinimumSize(800, 600)
        icon = app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        central = QWidget()
        central.setObjectName("centralRoot")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_banner())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards_host = QWidget()
        self._cards_layout = QHBoxLayout(self._cards_host)
        self._cards_layout.setContentsMargins(8, 8, 8, 8)
        self._cards_layout.setSpacing(8)
        for _ in range(_MAX_CARD_COLUMNS):
            column = QWidget()
            column_layout = QVBoxLayout(column)
            column_layout.setContentsMargins(0, 0, 0, 0)
            column_layout.setSpacing(8)
            column_layout.addStretch(1)
            self._columns_widgets.append(column)
            self._column_layouts.append(column_layout)
            self._cards_layout.addWidget(column, stretch=1)
        self._scroll.setWidget(self._cards_host)
        root.addWidget(self._scroll, stretch=1)

        self._empty = QFrame()
        empty_layout = QVBoxLayout(self._empty)
        self._empty_logo = QLabel()
        self._empty_logo.setObjectName("emptyLogo")
        self._empty_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo = logo_pixmap(small=False, height=120)
        if not logo.isNull():
            self._empty_logo.setPixmap(logo)
        self._empty_title = QLabel("Keine offenen Bestellungen")
        self._empty_title.setObjectName("emptyState")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint = QLabel(
            "Warte auf RIKER… Die letzte bekannte Liste bleibt bei Offline sichtbar."
        )
        self._empty_hint.setObjectName("emptyStateHint")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setWordWrap(True)
        empty_layout.addStretch(1)
        empty_layout.addWidget(self._empty_logo)
        empty_layout.addWidget(self._empty_title)
        empty_layout.addWidget(self._empty_hint)
        empty_layout.addStretch(2)
        root.addWidget(self._empty)

        self._status = StatusBarWidget()
        root.addWidget(self._status)

        self._build_menu()
        self._connect_services()
        self._render_orders(self._orders.orders)
        self._update_empty_state(self._orders.orders)

        self.setWindowTitle("SPOCK2 – Küchen Display")
        self.resize(1280, 800)
        if config.ui.fullscreen:
            self.showFullScreen()
        else:
            self.show()
            self.showMaximized()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self.refresh_appearance)

    def _build_banner(self) -> QWidget:
        """Auffälliger Hinweisstreifen für Probleme (z. B. Druckfehler)."""
        self._banner = QFrame()
        self._banner.setObjectName("problemBanner")
        self._banner.setVisible(False)
        self._banner.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        row = QHBoxLayout(self._banner)
        row.setContentsMargins(12, 6, 8, 6)
        row.setSpacing(8)
        self._banner_text = QLabel("")
        self._banner_text.setObjectName("problemBannerText")
        self._banner_text.setWordWrap(True)
        row.addWidget(self._banner_text, stretch=1)
        close_btn = QPushButton("OK")
        close_btn.setObjectName("bannerButton")
        close_btn.clicked.connect(self._hide_banner)
        row.addWidget(close_btn)
        return self._banner

    def show_problem(self, message: str, *, timeout_ms: int = 45_000) -> None:
        """Zeigt eine Problemmeldung im Hauptfenster (nicht modal)."""
        self._show_banner(message, kind="problemBanner", timeout_ms=timeout_ms)

    def show_hint(self, message: str, *, timeout_ms: int = 6_000) -> None:
        """Kurze Bestätigung (z. B. Nachdruck eingereiht)."""
        self._show_banner(message, kind="hintBanner", timeout_ms=timeout_ms)

    def _show_banner(self, message: str, *, kind: str, timeout_ms: int) -> None:
        self._banner_text.setText(message)
        if self._banner.objectName() != kind:
            self._banner.setObjectName(kind)
            self._banner.style().unpolish(self._banner)
            self._banner.style().polish(self._banner)
        self._banner.setVisible(True)
        if timeout_ms > 0:
            self._banner_timer.start(timeout_ms)

    @Slot()
    def _hide_banner(self) -> None:
        self._banner_timer.stop()
        self._banner.setVisible(False)

    def refresh_appearance(self) -> None:
        """Wendet Theme + Skalierung auf die QApplication an."""
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        size = self.size()
        self._last_appear_size = (size.width(), size.height())
        apply_appearance(app, self._config.ui, window_size=size)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._reflow_cards()
        if not self._config.ui.scale_with_window:
            return
        size = event.size()
        prev = self._last_appear_size
        if prev is not None:
            dw = abs(size.width() - prev[0])
            dh = abs(size.height() - prev[1])
            if dw < 40 and dh < 40:
                return
        self._appear_timer.start(180)

    def _wanted_columns(self) -> int:
        return wanted_columns(self._scroll.viewport().width() or self.width())

    def _reflow_cards(self, *, force: bool = False) -> None:
        """Verteilt die Karten auf so viele Spalten, wie die Breite hergibt.

        Jede Karte landet in der momentan kürzesten Spalte – so entstehen
        keine großen Löcher, wenn eine Bestellung viel länger als die andere ist.
        """
        if not self._column_layouts:
            return
        columns = self._wanted_columns()
        if columns == self._columns and not force:
            return
        self._columns = columns

        for index, column_layout in enumerate(self._column_layouts):
            for position in reversed(range(column_layout.count())):
                item = column_layout.itemAt(position)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    column_layout.takeAt(position)
                    widget.setParent(self._cards_host)
            self._columns_widgets[index].setVisible(index < columns)

        heights = [0] * columns
        for order_id in self._card_order:
            card = self._cards.get(order_id)
            if card is None:
                continue
            target = heights.index(min(heights))
            column_layout = self._column_layouts[target]
            # Vor den Stretch am Ende einfügen.
            column_layout.insertWidget(column_layout.count() - 1, card)
            card.setVisible(True)
            heights[target] += card.sizeHint().height() + column_layout.spacing()

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Ansicht")
        fs_action = QAction("Vollbild umschalten", self)
        fs_action.setShortcut(QKeySequence(Qt.Key.Key_F11))
        fs_action.triggered.connect(self.toggle_fullscreen)
        file_menu.addAction(fs_action)

        quit_action = QAction("Beenden", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        if self._notes is not None and self._notes.enabled:
            notes_menu = menubar.addMenu("Zettel")
            write_action = QAction("Zettel schreiben…", self)
            write_action.triggered.connect(self._on_write_note)
            notes_menu.addAction(write_action)

        admin_menu = menubar.addMenu("Admin")
        admin_action = QAction("Einstellungen…", self)
        admin_action.triggered.connect(self._on_admin)
        admin_menu.addAction(admin_action)

    def _connect_services(self) -> None:
        self._orders.orders_changed.connect(self._on_orders_changed)
        self._orders.connection_changed.connect(self._on_riker_connection)
        self._orders.complete_finished.connect(self._on_complete_finished)

        if self._notes is not None and self._notes.enabled:
            self._notes.new_notes_detected.connect(self._on_new_notes)
            self._notes.connection_changed.connect(self._on_picard_connection)
            self._notes.create_finished.connect(self._on_note_create_finished)
            self._notes.close_finished.connect(self._on_note_close_finished)

        if self._monitor is not None:
            self._monitor.status_changed.connect(self._on_app_status)

    @Slot(object)
    def _on_orders_changed(self, orders: object) -> None:
        if isinstance(orders, list):
            self._render_orders(orders)
            self._update_empty_state(orders)
            self._status.update_order_count(len(orders))
            if self._monitor is not None:
                self._monitor.set_orders_cache(
                    len(orders), self._orders.cache_updated_at
                )

    @Slot(object)
    def _on_riker_connection(self, status: object) -> None:
        if isinstance(status, ApiStatus):
            self._offline = status.state.value == "offline"
            self._status.update_riker(status)
            self._update_empty_state(self._orders.orders)
            self._maybe_warn_tls("RIKER", status)
            if self._monitor is not None:
                self._monitor.set_riker_status(status)

    @Slot(object)
    def _on_picard_connection(self, status: object) -> None:
        if isinstance(status, ApiStatus):
            self._status.update_picard(status)
            self._maybe_warn_tls("PICARD", status)
            if self._monitor is not None:
                self._monitor.set_picard_status(status)

    def _maybe_warn_tls(self, name: str, status: ApiStatus) -> None:
        """Sagt bei Zertifikatsfehlern, wo die Lösung liegt – aber nur einmal.

        Der Poller wiederholt den Fehler alle paar Sekunden; ohne diese Sperre
        wäre der Streifen dauerhaft im Bild.
        """
        if status.error_kind != "TlsError":
            self._tls_warned.discard(name)
            return
        if name in self._tls_warned:
            return
        self._tls_warned.add(name)
        self.show_problem(
            f"{name}: Zertifikat nicht vertrauenswürdig. Admin → Einstellungen → "
            "APIs → TLS: CA-Bundle hinterlegen oder Prüfung abschalten."
        )

    @Slot(object)
    def _on_app_status(self, status: object) -> None:
        if isinstance(status, AppStatus):
            self._status.update_from_app_status(status)

    def set_printer_statuses(self, statuses: list[PrinterStatus]) -> None:
        self._status.update_printers(statuses)
        self._maybe_warn_printers(statuses)
        if self._monitor is not None:
            self._monitor.set_printer_statuses(statuses)

    def _maybe_warn_printers(self, statuses: list[PrinterStatus]) -> None:
        """Ein Streifen pro neuem Druckerproblem – der Status wird zyklisch geprüft."""
        broken = {
            f"{s.role}: {s.last_error or 'nicht bereit'}"
            for s in statuses
            if not (s.online and s.accepting_jobs)
        }
        new = broken - self._printer_warned
        self._printer_warned = broken
        if new:
            self.show_problem(
                "Drucker nicht bereit – "
                + "; ".join(sorted(new))
                + ". Admin → Einstellungen → Drucker."
            )

    def set_pending_jobs(self, count: int) -> None:
        self._status.update_pending_jobs(count)
        if self._monitor is not None:
            self._monitor.set_pending_print_jobs(count)

    def set_failed_jobs(self, count: int) -> None:
        self._status.update_failed_jobs(count)

    def _render_orders(self, orders: list[Any]) -> None:
        typed: list[Order] = [o for o in orders if isinstance(o, Order)]
        wanted = {o.id for o in typed}

        for oid in list(self._cards):
            if oid not in wanted:
                self._discard_card(self._cards.pop(oid))

        for order in typed:
            completing = self._orders.is_completing(order.id)
            if order.id in self._cards:
                # Neu aufbauen für aktuelle Wartezeit / Items
                self._discard_card(self._cards.pop(order.id))
            card = OrderCard(order, completing=completing)
            card.done_clicked.connect(self._on_done_clicked)
            card.reprint_clicked.connect(self._on_reprint_clicked)
            self._cards[order.id] = card

        self._card_order = [o.id for o in typed]
        self._reflow_cards(force=True)

    @staticmethod
    def _discard_card(card: OrderCard) -> None:
        parent_layout = card.parentWidget().layout() if card.parentWidget() else None
        if parent_layout is not None:
            parent_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()

    def _update_empty_state(self, orders: list[Any]) -> None:
        has_orders = any(isinstance(o, Order) for o in orders)
        self._empty.setVisible(not has_orders)
        self._scroll.setVisible(has_orders)
        if has_orders:
            return
        if self._offline:
            self._empty_title.setText("Offline – keine zwischengespeicherte Liste")
            self._empty_hint.setText(
                "RIKER ist nicht erreichbar. Sobald die Verbindung steht, "
                "erscheinen offene Bestellungen hier."
            )
        else:
            self._empty_title.setText("Keine offenen Bestellungen")
            self._empty_hint.setText(
                "Alles ruhig in der Küche. Neue Bestellungen von RIKER "
                "erscheinen automatisch als Karten."
            )

    @Slot(int)
    def _on_done_clicked(self, order_id: int) -> None:
        order = self._orders.get_order(order_id)
        if order is None:
            return
        if self._config.ui.confirm_complete and not CompleteConfirmDialog.ask(order, self):
            return
        if not self._orders.complete_order(order_id):
            QMessageBox.information(
                self,
                "Erledigt",
                "Bestellung wird bereits erledigt oder ist unbekannt.",
            )

    @Slot(int, bool, object)
    def _on_complete_finished(self, order_id: int, ok: bool, error: object) -> None:
        if not ok:
            QMessageBox.warning(
                self,
                "Erledigt fehlgeschlagen",
                f"Bestellung #{order_id} konnte nicht erledigt werden.\n{error}",
            )

    @Slot(int)
    def _on_reprint_clicked(self, order_id: int) -> None:
        order = self._orders.get_order(order_id)
        if order is None or self._orchestrator is None:
            QMessageBox.information(self, "Nachdruck", "Druck ist nicht verfügbar.")
            return
        try:
            self._orchestrator.enqueue_order(order, reprint=True)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Nachdruck fehlgeschlagen", str(exc))
            return
        logger.info("event=reprint_enqueued order_id=%s", order_id)
        self.show_hint(f"Nachdruck für #{order_id} eingereiht.")

    @Slot()
    def _on_write_note(self) -> None:
        if self._notes is None:
            return
        result = NoteDialog.prompt(self)
        if result is None:
            return
        text, target, priority = result
        if not self._notes.create_note(text, target=target, priority=priority):
            QMessageBox.warning(self, "Zettel", "Zettel konnte nicht gesendet werden.")

    @Slot(bool, object, object)
    def _on_note_create_finished(self, ok: bool, note: object, error: object) -> None:
        if ok:
            QMessageBox.information(self, "Zettel", "Zettel wurde gesendet.")
        else:
            QMessageBox.warning(self, "Zettel", f"Senden fehlgeschlagen:\n{error}")

    @Slot(str, bool, object)
    def _on_note_close_finished(self, note_id: str, ok: bool, error: object) -> None:
        if not ok:
            QMessageBox.warning(
                self, "Zettel", f"Schließen von {note_id} fehlgeschlagen:\n{error}"
            )

    @Slot(object)
    def _on_new_notes(self, notes: object) -> None:
        if not isinstance(notes, list):
            return
        for note in notes:
            if not isinstance(note, Note):
                continue
            if note.id in self._open_note_popups:
                continue
            self._show_note_popup(note)

    def _show_note_popup(self, note: Note) -> None:
        self._open_note_popups.add(note.id)
        popup = NotePopup(note, self)

        def _cleanup(_result: int = 0) -> None:
            self._open_note_popups.discard(note.id)

        popup.finished.connect(_cleanup)
        popup.close_requested.connect(self._close_note)
        popup.print_requested.connect(self._print_note)
        popup.open()

    @Slot(str)
    def _close_note(self, note_id: str) -> None:
        if self._notes is not None:
            self._notes.close_note(note_id)

    @Slot(str)
    def _print_note(self, note_id: str) -> None:
        if self._notes is None or self._orchestrator is None:
            return
        note = next((n for n in self._notes.notes if n.id == note_id), None)
        if note is None:
            return
        try:
            self._orchestrator.enqueue_note(note, reprint=True)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Zettel-Druck", str(exc))

    @Slot()
    def _on_admin(self) -> None:
        AdminDialog.open_admin(
            self._config,
            on_test_print=self._test_print,
            on_apply=self._on_settings_apply,
            on_connection_test=self._on_connection_test,
            list_queues=list_system_queues,
            parent=self,
            admin_pin=self._config.ui.admin_pin,
        )

    def _test_print(self, role: str) -> None:
        if self._orchestrator is None:
            raise RuntimeError("PrintOrchestrator nicht verfügbar")
        self._orchestrator.enqueue_test(role)

    @Slot()
    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.accept()
