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
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
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

__all__ = ["MainWindow", "load_stylesheet"]


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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._orders = order_service
        self._notes = note_service
        self._monitor = connection_monitor
        self._orchestrator = orchestrator
        self._on_settings_apply = on_settings_apply
        self._cards: dict[int, OrderCard] = {}
        self._offline = False
        self._open_note_popups: set[str] = set()
        self._appear_timer = QTimer(self)
        self._appear_timer.setSingleShot(True)
        self._appear_timer.timeout.connect(self.refresh_appearance)
        self._last_appear_size: tuple[int, int] | None = None

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

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards_host = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_host)
        self._cards_layout.setContentsMargins(12, 12, 12, 12)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch(1)
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
            if self._monitor is not None:
                self._monitor.set_riker_status(status)

    @Slot(object)
    def _on_picard_connection(self, status: object) -> None:
        if isinstance(status, ApiStatus):
            self._status.update_picard(status)
            if self._monitor is not None:
                self._monitor.set_picard_status(status)

    @Slot(object)
    def _on_app_status(self, status: object) -> None:
        if isinstance(status, AppStatus):
            self._status.update_from_app_status(status)

    def set_printer_statuses(self, statuses: list[PrinterStatus]) -> None:
        self._status.update_printers(statuses)
        if self._monitor is not None:
            self._monitor.set_printer_statuses(statuses)

    def set_pending_jobs(self, count: int) -> None:
        self._status.update_pending_jobs(count)
        if self._monitor is not None:
            self._monitor.set_pending_print_jobs(count)

    def _render_orders(self, orders: list[Any]) -> None:
        typed: list[Order] = [o for o in orders if isinstance(o, Order)]
        wanted = {o.id for o in typed}

        # Entferne obsolete Cards
        for oid in list(self._cards):
            if oid not in wanted:
                card = self._cards.pop(oid)
                self._cards_layout.removeWidget(card)
                card.deleteLater()

        # Stretch ans Ende: vor dem Stretch einfügen
        stretch_index = self._cards_layout.count() - 1
        for order in typed:
            completing = self._orders.is_completing(order.id)
            if order.id in self._cards:
                # Neu aufbauen für aktuelle Wartezeit / Items
                old = self._cards.pop(order.id)
                self._cards_layout.removeWidget(old)
                old.deleteLater()
            card = OrderCard(order, completing=completing)
            card.done_clicked.connect(self._on_done_clicked)
            card.reprint_clicked.connect(self._on_reprint_clicked)
            self._cards[order.id] = card
            self._cards_layout.insertWidget(max(0, stretch_index), card)
            stretch_index = self._cards_layout.count() - 1

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
