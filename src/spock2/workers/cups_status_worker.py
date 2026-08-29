"""CupsStatusWorker: pollt submitted/printing Jobs gegen Transport."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from spock2.api.errors import DbError, InvalidTransitionError
from spock2.config.models import AppConfig
from spock2.domain.print_job import PrintJob, PrintJobStatus
from spock2.persistence import print_jobs
from spock2.persistence.db import connection
from spock2.printing.transport import PrintTransport
from spock2.services.printer_health import transport_snapshot

logger = logging.getLogger(__name__)

# Transport-State → PrintJobStatus
_STATE_TO_STATUS: dict[str, PrintJobStatus] = {
    "printing": PrintJobStatus.PRINTING,
    "completed": PrintJobStatus.COMPLETED,
    "failed": PrintJobStatus.FAILED,
    "cancelled": PrintJobStatus.CANCELLED,
    "unknown": PrintJobStatus.UNKNOWN,
    # pending/held bleiben submitted
}


class CupsStatusWorker(QObject):
    """Aktualisiert Job-Status anhand von Transport.get_job_state."""

    job_updated = Signal(object)
    error = Signal(str)
    health_snapshot = Signal(object)  # dict aus transport_snapshot

    def __init__(
        self,
        db_path: str | Path,
        config: AppConfig,
        transport: PrintTransport,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.db_path = Path(db_path)
        self.config = config
        self.transport = transport
        self._running = False

    @Slot()
    def start_polling(self) -> None:
        self._running = True
        self.poll_once()

    @Slot()
    def stop(self) -> None:
        self._running = False

    @Slot()
    def poll_health(self) -> None:
        """Fragt Transport-/Queue-Zustand ab und schickt ihn an den UI-Thread."""
        self.health_snapshot.emit(transport_snapshot(self.transport))

    @Slot()
    def poll_once(self) -> int:
        """Prüft alle submitted/printing Jobs. Gibt Anzahl Updates zurück."""
        if not self.transport.is_available():
            return 0

        updated_count = 0
        try:
            with connection(self.db_path) as conn:
                jobs = print_jobs.list_jobs(conn, status=PrintJobStatus.SUBMITTED, limit=200)
                jobs += print_jobs.list_jobs(conn, status=PrintJobStatus.PRINTING, limit=200)
        except DbError as exc:
            self.error.emit(exc.message)
            return 0

        for job in jobs:
            if self._update_from_transport(job):
                updated_count += 1
        return updated_count

    def _update_from_transport(self, job: PrintJob) -> bool:
        if job.id is None or job.cups_job_id is None:
            return False

        try:
            state = self.transport.get_job_state(job.cups_job_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Job-State %s: %s", job.cups_job_id, exc)
            state = "unknown"

        new_status = _STATE_TO_STATUS.get(state)
        if new_status is None:
            return False
        if new_status == job.status:
            return False
        if not job.can_transition_to(new_status):
            return False

        try:
            with connection(self.db_path) as conn:
                kwargs: dict = {}
                if new_status == PrintJobStatus.FAILED:
                    kwargs["last_error"] = f"CUPS state={state}"
                updated = print_jobs.transition(conn, job.id, new_status, **kwargs)
            self.job_updated.emit(updated)
            return True
        except (DbError, InvalidTransitionError) as exc:
            self.error.emit(exc.message)
            return False
