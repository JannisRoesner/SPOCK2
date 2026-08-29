"""PrintWorker: drained pending Jobs → Render → Transport."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from spock2.api.errors import CupsUnavailable, DbError, InvalidTransitionError, PrintFailed
from spock2.config.models import AppConfig
from spock2.domain.notes import Note
from spock2.domain.orders import Order
from spock2.domain.print_job import PrinterRole, PrintJob, PrintJobStatus, SourceType
from spock2.persistence import print_jobs
from spock2.persistence.db import connection
from spock2.printing.profiles import get_profile
from spock2.printing.renderer import ReceiptRenderer
from spock2.printing.transport import PrintTransport

logger = logging.getLogger(__name__)


class PrintWorker(QObject):
    """Holt pending Jobs, rendert und submitted über den Transport.

    Signals:
        job_updated(PrintJob)
        error(str)
    """

    job_updated = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        db_path: str | Path,
        config: AppConfig,
        transport: PrintTransport,
        renderer: ReceiptRenderer | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.db_path = Path(db_path)
        self.config = config
        self.transport = transport
        self.renderer = renderer or ReceiptRenderer()
        self._running = False

    @property
    def max_attempts(self) -> int:
        return self.config.print.max_attempts

    @Slot()
    def start_draining(self) -> None:
        self._running = True
        self.drain()

    @Slot()
    def stop(self) -> None:
        self._running = False

    @Slot()
    def drain(self, *, batch_size: int = 8) -> int:
        """Verarbeitet bis zu ``batch_size`` pending Jobs. Gibt Anzahl zurück."""
        processed = 0
        while True:
            n = self.process_once(limit=batch_size)
            processed += n
            if n == 0 or not self._running:
                break
            if n < batch_size:
                break
        return processed

    def process_once(self, *, limit: int = 1) -> int:
        """Ein Drain-Schritt: claim → render → submit → Status."""
        if not self.transport.is_available():
            self.error.emit("Druck-Transport nicht verfügbar")
            return 0

        try:
            with connection(self.db_path) as conn:
                pending = print_jobs.claim_pending(conn, limit=limit)
        except DbError as exc:
            self.error.emit(exc.message)
            return 0

        count = 0
        for job in pending:
            try:
                self._process_job(job)
                count += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("PrintJob %s fehlgeschlagen", job.id)
                self.error.emit(str(exc))
                self._fail_job(job, str(exc))
        return count

    def _process_job(self, job: PrintJob) -> None:
        assert job.id is not None
        profile = get_profile(job.profile_name)
        payload = json.loads(job.payload_json)
        text = self._render_payload(job, payload, profile)
        if self._prefer_escpos(profile):
            data = self.renderer.render_escpos(text, profile)
        else:
            data = self.renderer.render_to_bytes(text, profile)

        queue = self._queue_for_role(job.target_role)
        title = f"SPOCK2 {job.source_type.value} {job.source_id}"

        try:
            cups_id = self.transport.submit(queue, data, title)
        except (PrintFailed, CupsUnavailable) as exc:
            self._fail_job(job, exc.message or str(exc))
            return

        if cups_id is None:
            self._fail_job(job, "Transport lieferte keine Job-ID")
            return

        try:
            with connection(self.db_path) as conn:
                updated = print_jobs.mark_submitted(conn, job.id, cups_job_id=cups_id)
                # FileTransport: sofort completed
                state = self.transport.get_job_state(cups_id)
                if state == "completed":
                    updated = print_jobs.transition(
                        conn, job.id, PrintJobStatus.COMPLETED
                    )
        except (DbError, InvalidTransitionError) as exc:
            self.error.emit(exc.message)
            return

        self.job_updated.emit(updated)

    def _fail_job(self, job: PrintJob, message: str) -> None:
        if job.id is None:
            return
        try:
            with connection(self.db_path) as conn:
                updated = print_jobs.mark_failed(conn, job.id, message)
                if updated.attempts < self.max_attempts:
                    updated = print_jobs.requeue_failed(conn, job.id)
                self.job_updated.emit(updated)
        except (DbError, InvalidTransitionError) as exc:
            self.error.emit(exc.message)

    def _render_payload(
        self,
        job: PrintJob,
        payload: dict[str, Any],
        profile: Any,
    ) -> str:
        if job.source_type == SourceType.MANUAL_TEST:
            return str(payload.get("text") or self.renderer.format_test(job.target_role, profile))

        if job.source_type == SourceType.PICARD_NOTE:
            note = Note.model_validate(
                {k: v for k, v in payload.items() if not k.startswith("_")}
            )
            return self.renderer.format_note(note, profile)

        # Order
        clean = {k: v for k, v in payload.items() if not k.startswith("_")}
        order = Order.model_validate(clean)
        return self.renderer.format_order(order, profile, role=job.target_role)

    def _queue_for_role(self, role: PrinterRole) -> str:
        printer = self.config.printer_for_role(role.value)  # type: ignore[arg-type]
        if printer is not None:
            return printer.queue
        return f"spock-{role.value}"

    def _prefer_escpos(self, profile: Any) -> bool:
        """ESC/POS für WinSpool; sonst wenn Profil escpos und nicht CUPS-Text."""
        from spock2.printing.cups_transport import CupsTransport
        from spock2.printing.winspool_transport import WinSpoolTransport

        if isinstance(self.transport, WinSpoolTransport):
            return True
        if isinstance(self.transport, CupsTransport):
            return False
        caps = getattr(profile, "capabilities", ()) or ()
        return "escpos" in caps
