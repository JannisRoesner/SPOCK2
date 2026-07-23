"""SPOCK2 Anwendungs-Bootstrap: Config, Services, Worker, UI."""

from __future__ import annotations

import contextlib
import logging
import os
import sys

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Slot
from PySide6.QtWidgets import QApplication

from spock2.api.backoff import ExponentialBackoff
from spock2.api.errors import CupsUnavailable
from spock2.api.picard import PicardClient
from spock2.api.riker import RikerClient
from spock2.config.loader import load_config
from spock2.config.models import AppConfig
from spock2.domain.notes import Note
from spock2.domain.orders import Order
from spock2.domain.print_job import PrintJobStatus
from spock2.domain.status import ApiStatus, ConnectionState
from spock2.logging_setup import setup_logging
from spock2.persistence import print_jobs
from spock2.persistence.db import connection as db_connection
from spock2.persistence.db import migrate
from spock2.printing.cups_transport import CupsTransport, cups_available
from spock2.printing.file_transport import FileTransport
from spock2.printing.orchestrator import PrintOrchestrator
from spock2.printing.renderer import ReceiptRenderer
from spock2.printing.transport import PrintTransport
from spock2.services.connection_monitor import ConnectionMonitor
from spock2.services.note_service import NoteService
from spock2.services.order_service import OrderService
from spock2.services.printer_health import PrinterHealth
from spock2.ui.main_window import MainWindow, load_stylesheet
from spock2.workers.cups_status_worker import CupsStatusWorker
from spock2.workers.note_poll_worker import NotePollWorker
from spock2.workers.poll_worker import PollWorker
from spock2.workers.print_worker import PrintWorker

logger = logging.getLogger(__name__)


def create_transport(config: AppConfig) -> PrintTransport:
    """FileTransport unter Windows / ohne CUPS; sonst CupsTransport."""
    use_cups = sys.platform.startswith("linux") and cups_available()
    if use_cups:
        try:
            transport: PrintTransport = CupsTransport()
            logger.info("event=transport_cups")
            return transport
        except CupsUnavailable as exc:
            logger.warning("event=cups_fallback_file err=%s", exc)
    transport = FileTransport()
    logger.info("event=transport_file dir=%s", getattr(transport, "output_dir", "?"))
    return transport


def create_riker(config: AppConfig) -> RikerClient:
    ca = config.tls.ca_bundle or None
    return RikerClient(
        config.riker.base_url,
        ssl_verify=config.tls.ssl_verify,
        connect_timeout=config.riker.connect_timeout_s,
        read_timeout=config.riker.read_timeout_s,
        ca_bundle=ca,
    )


def create_picard(config: AppConfig) -> PicardClient | None:
    if not config.picard.enabled:
        return None
    ca = config.tls.ca_bundle or None
    return PicardClient(
        config.picard.base_url,
        ssl_verify=config.tls.ssl_verify,
        connect_timeout=config.picard.connect_timeout_s,
        read_timeout=config.picard.read_timeout_s,
        ca_bundle=ca,
        session_id=config.picard.session_id or None,
        kitchen_note_types=list(config.picard.kitchen_note_types),
        enabled=True,
    )


class ApplicationController(QObject):
    """Hält Worker-Threads und verdrahtet Services ↔ UI."""

    def __init__(self, config: AppConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.db_path = config.db.resolved_path()
        migrate(self.db_path)

        self.riker = create_riker(config)
        self.picard = create_picard(config)
        self.transport = create_transport(config)
        self.renderer = ReceiptRenderer()
        self.orchestrator = PrintOrchestrator(
            self.db_path,
            config,
            transport=self.transport,
            renderer=self.renderer,
            ensure_schema=False,
        )

        role_queues = {
            p.role: p.cups_queue
            for p in config.printers.values()
            if p.enabled
        }
        self.monitor = ConnectionMonitor(self)
        self.printer_health = PrinterHealth(role_queues=role_queues, parent=self)
        self.order_service = OrderService(
            self.riker,
            on_new_orders=self._on_new_orders,
            parent=self,
        )
        self.note_service = NoteService(
            self.picard,
            enabled=config.picard.enabled and self.picard is not None,
            on_new_notes=self._on_new_notes,
            parent=self,
        )

        self.order_service.connection_changed.connect(self.monitor.set_riker_status)
        self.note_service.connection_changed.connect(self.monitor.set_picard_status)
        self.printer_health.statuses_changed.connect(self.monitor.set_printer_statuses)

        self._threads: list[QThread] = []
        self._poll_worker: PollWorker | None = None
        self._note_poll_worker: NotePollWorker | None = None
        self._print_worker: PrintWorker | None = None
        self._cups_status_worker: CupsStatusWorker | None = None
        self._drain_timer: QTimer | None = None
        self._cups_timer: QTimer | None = None
        self._health_timer: QTimer | None = None

        self.window = MainWindow(
            config,
            self.order_service,
            note_service=self.note_service,
            connection_monitor=self.monitor,
            orchestrator=self.orchestrator,
        )

        self.printer_health.statuses_changed.connect(self.window.set_printer_statuses)
        self._start_workers()
        self._refresh_pending_count()

    def _start_workers(self) -> None:
        cfg = self.config
        backoff = ExponentialBackoff(
            initial=cfg.backoff.initial_s,
            factor=cfg.backoff.factor,
            max=cfg.backoff.max_s,
            reset_on_success=cfg.backoff.reset_on_success,
        )

        # --- RIKER Poll (eigener Thread, kein HTTP im UI) ---
        poll_thread = QThread(self)
        self._poll_worker = PollWorker(
            self.riker,
            interval_s=cfg.polling.interval_s,
            backoff=backoff,
        )
        self._poll_worker.moveToThread(poll_thread)
        self._poll_worker.orders_fetched.connect(self.order_service.apply_poll_result)
        self._poll_worker.poll_error.connect(self.order_service.apply_poll_error)
        self._poll_worker.status_changed.connect(self._on_poll_status)
        poll_thread.started.connect(self._poll_worker.start_polling)
        self._threads.append(poll_thread)
        poll_thread.start()

        # --- PICARD Note-Poll ---
        if self.picard is not None and cfg.picard.enabled:
            note_backoff = ExponentialBackoff(
                initial=cfg.backoff.initial_s,
                factor=cfg.backoff.factor,
                max=cfg.backoff.max_s,
                reset_on_success=cfg.backoff.reset_on_success,
            )
            note_thread = QThread(self)
            self._note_poll_worker = NotePollWorker(
                self.picard,
                interval_s=cfg.polling.interval_s,
                backoff=note_backoff,
            )
            self._note_poll_worker.moveToThread(note_thread)
            self._note_poll_worker.notes_fetched.connect(
                self.note_service.apply_poll_result
            )
            self._note_poll_worker.poll_error.connect(self.note_service.apply_poll_error)
            self._note_poll_worker.status_changed.connect(self._on_note_poll_status)
            note_thread.started.connect(self._note_poll_worker.start_polling)
            self._threads.append(note_thread)
            note_thread.start()

        # --- Print drain ---
        print_thread = QThread(self)
        self._print_worker = PrintWorker(
            self.db_path,
            cfg,
            self.transport,
            renderer=self.renderer,
        )
        self._print_worker.moveToThread(print_thread)
        self._print_worker.job_updated.connect(self._on_job_updated)
        self._print_worker.error.connect(self._on_print_error)
        self._threads.append(print_thread)
        print_thread.start()

        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(1500)
        self._drain_timer.timeout.connect(self._print_worker.drain)
        self._drain_timer.start()

        # --- CUPS / Transport Status ---
        status_thread = QThread(self)
        self._cups_status_worker = CupsStatusWorker(
            self.db_path,
            cfg,
            self.transport,
        )
        self._cups_status_worker.moveToThread(status_thread)
        self._cups_status_worker.job_updated.connect(self._on_job_updated)
        self._threads.append(status_thread)
        status_thread.start()

        self._cups_timer = QTimer(self)
        self._cups_timer.setInterval(3000)
        self._cups_timer.timeout.connect(self._cups_status_worker.poll_once)
        self._cups_timer.start()

        self._health_timer = QTimer(self)
        self._health_timer.setInterval(5000)
        self._health_timer.timeout.connect(self._refresh_printer_health)
        self._health_timer.start()
        self._refresh_printer_health()

    @Slot(object)
    def _on_poll_status(self, status: object) -> None:
        if isinstance(status, ApiStatus):
            if status.state == ConnectionState.CONNECTING:
                self.order_service.mark_connecting()
            self.monitor.set_riker_status(status)

    @Slot(object)
    def _on_note_poll_status(self, status: object) -> None:
        if isinstance(status, ApiStatus):
            self.monitor.set_picard_status(status)

    def _on_new_orders(self, orders: list[Order]) -> None:
        if not self.config.print.auto_print_new_orders:
            return
        for order in orders:
            try:
                ids = self.orchestrator.enqueue_order(order, reprint=False)
                logger.info(
                    "event=auto_print_order order_id=%s jobs=%s", order.id, ids
                )
            except Exception:  # noqa: BLE001
                logger.exception("event=auto_print_order_failed order_id=%s", order.id)
        self._kick_print_drain()
        self._refresh_pending_count()

    def _on_new_notes(self, notes: list[Note]) -> None:
        if not self.config.print.auto_print_new_notes:
            return
        for note in notes:
            try:
                ids = self.orchestrator.enqueue_note(note, reprint=False)
                logger.info("event=auto_print_note note_id=%s jobs=%s", note.id, ids)
            except Exception:  # noqa: BLE001
                logger.exception("event=auto_print_note_failed note_id=%s", note.id)
        self._kick_print_drain()
        self._refresh_pending_count()

    @Slot(object)
    def _on_job_updated(self, _job: object) -> None:
        self._refresh_pending_count()

    @Slot(str)
    def _on_print_error(self, message: str) -> None:
        logger.warning("event=print_worker_error msg=%s", message)

    def _kick_print_drain(self) -> None:
        if self._print_worker is not None:
            QTimer.singleShot(0, self._print_worker.drain)

    def _refresh_pending_count(self) -> None:
        try:
            with db_connection(self.db_path) as conn:
                pending = print_jobs.count_by_status(conn, PrintJobStatus.PENDING)
                submitted = print_jobs.count_by_status(conn, PrintJobStatus.SUBMITTED)
                printing = print_jobs.count_by_status(conn, PrintJobStatus.PRINTING)
            total = pending + submitted + printing
        except Exception as exc:  # noqa: BLE001
            logger.warning("event=pending_count_failed err=%s", exc)
            return
        self.monitor.set_pending_print_jobs(total)
        self.window.set_pending_jobs(total)

    @Slot()
    def _refresh_printer_health(self) -> None:
        try:
            self.printer_health.refresh_from_transport(self.transport)
        except Exception as exc:  # noqa: BLE001
            logger.warning("event=printer_health_failed err=%s", exc)

    def shutdown(self) -> None:
        logger.info("event=app_shutdown")
        if self._drain_timer is not None:
            self._drain_timer.stop()
        if self._cups_timer is not None:
            self._cups_timer.stop()
        if self._health_timer is not None:
            self._health_timer.stop()

        if self._poll_worker is not None:
            self._poll_worker.stop_polling()
        if self._note_poll_worker is not None:
            self._note_poll_worker.stop_polling()
        if self._print_worker is not None:
            self._print_worker.stop()
        if self._cups_status_worker is not None:
            self._cups_status_worker.stop()

        for thread in self._threads:
            thread.quit()
            if not thread.wait(3000):
                logger.warning("event=thread_join_timeout")
                thread.terminate()
                thread.wait(1000)

        self.order_service.shutdown()
        self.note_service.shutdown()
        with contextlib.suppress(Exception):
            self.riker.close()
        if self.picard is not None:
            with contextlib.suppress(Exception):
                self.picard.close()


def main(argv: list[str] | None = None) -> int:
    """Lädt Config, Logging, DB und startet die PySide6-UI."""
    _ = argv  # reserved for future CLI flags
    config = load_config()
    setup_logging(
        level=config.logging.level,
        file_path=config.logging.resolved_file_path(),
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
        fmt=config.logging.format,
    )
    logger.info("event=app_start version=%s", __import__("spock2").__version__)
    logger.info(
        "event=config_loaded riker=%s picard_enabled=%s station_role=%s fullscreen=%s",
        config.riker.base_url,
        config.picard.enabled,
        config.routing.station_role,
        config.ui.fullscreen,
    )

    # Offscreen/headless tests: QT_QPA_PLATFORM=offscreen
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("SPOCK2")
    app.setOrganizationName("SPOCK2")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

    qss = load_stylesheet()
    # region agent log
    from spock2.ui.debug_probe import agent_log

    agent_log(
        "app.py:main",
        "pre_stylesheet",
        {
            "qtStyle": app.style().objectName(),
            "qssLen": len(qss),
            "qssLoaded": bool(qss),
            "platform": sys.platform,
            "qtQpaPlatform": os.environ.get("QT_QPA_PLATFORM", ""),
        },
        hypothesis_id="A,D",
    )
    # endregion
    if qss:
        app.setStyleSheet(qss)
    # region agent log
    agent_log(
        "app.py:main",
        "post_stylesheet",
        {"qtStyle": app.style().objectName(), "qssLen": len(qss)},
        hypothesis_id="A,B",
    )
    # endregion

    controller = ApplicationController(config)
    app.aboutToQuit.connect(controller.shutdown)

    # Window already shown in MainWindow.__init__ via fullscreen/maximized
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
