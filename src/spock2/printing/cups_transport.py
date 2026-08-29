"""CUPS-Transport via pycups (kein Shell)."""

from __future__ import annotations

import contextlib
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from spock2.api.errors import CupsUnavailable, PrintFailed

logger = logging.getLogger(__name__)

try:
    import cups as _cups  # type: ignore[import-untyped]

    _CUPS_IMPORT_ERROR: BaseException | None = None
except Exception as exc:  # noqa: BLE001 – Import kann fehlen / fehlschlagen
    _cups = None  # type: ignore[assignment]
    _CUPS_IMPORT_ERROR = exc


def cups_payload_format(data: bytes) -> tuple[str, str]:
    """MIME-Typ und Dateiendung für CUPS ``printFile``."""
    if data.startswith(b"%PDF"):
        return "application/pdf", ".pdf"
    return "text/plain", ".txt"


# IPP-Job-State → SPOCK2-Statusnamen (Transport-Ebene)
_IPP_STATE_MAP: dict[int, str] = {
    3: "pending",  # IPP_JOB_PENDING
    4: "held",  # IPP_JOB_HELD
    5: "printing",  # IPP_JOB_PROCESSING
    6: "printing",  # IPP_JOB_STOPPED → behandeln als aktiv/problem
    7: "cancelled",  # IPP_JOB_CANCELED
    8: "failed",  # IPP_JOB_ABORTED
    9: "completed",  # IPP_JOB_COMPLETED
}


class CupsTransport:
    """pycups-basierter Transport: ``printFile`` + Job-Status.

    Eine ``cups.Connection`` kapselt einen libcups-HTTP-Socket und ist **nicht**
    thread-safe. SPOCK2 nutzt denselben Transport aus UI-, Print- und
    Status-Thread, daher hält jeder Thread seine eigene Verbindung.
    """

    def __init__(self, *, connection: Any | None = None) -> None:
        if _cups is None:
            raise CupsUnavailable(
                "pycups nicht verfügbar",
                cause=_CUPS_IMPORT_ERROR,
            )
        self._local = threading.local()
        # Injizierte Verbindung (Tests): bewusst geteilt, kein Thread-Local.
        self._injected: Any | None = connection
        if connection is None:
            self._local.conn = self._new_connection()

    @staticmethod
    def _new_connection() -> Any:
        try:
            return _cups.Connection()
        except Exception as exc:  # noqa: BLE001
            raise CupsUnavailable("CUPS-Verbindung fehlgeschlagen", cause=exc) from exc

    @property
    def _conn(self) -> Any:
        """Verbindung des aufrufenden Threads (lazy pro Thread)."""
        injected = getattr(self, "_injected", None)
        if injected is not None:
            return injected
        local = getattr(self, "_local", None)
        if local is None:
            local = threading.local()
            self._local = local
        conn = getattr(local, "conn", None)
        if conn is None:
            conn = self._new_connection()
            local.conn = conn
        return conn

    def submit(self, queue_name: str, data: bytes, title: str) -> int | None:
        if not queue_name:
            raise PrintFailed("Leerer Queue-Name")
        tmp_path: str | None = None
        try:
            mime, suffix = cups_payload_format(data)
            fd, tmp_path = tempfile.mkstemp(prefix="spock2_", suffix=suffix)
            try:
                os.write(fd, data)
            finally:
                os.close(fd)
            # Sichere Permissions (nur Owner)
            with contextlib.suppress(OSError):
                os.chmod(tmp_path, 0o600)
            job_id = self._conn.printFile(
                queue_name,
                tmp_path,
                title or "SPOCK2",
                {"document-format": mime},
            )
            return int(job_id) if job_id else None
        except Exception as exc:  # noqa: BLE001
            raise PrintFailed(
                f"CUPS-Submit an '{queue_name}' fehlgeschlagen",
                cause=exc,
            ) from exc
        finally:
            if tmp_path:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Tempfile cleanup fehlgeschlagen: %s", exc)

    def get_job_state(self, job_id: int) -> str:
        try:
            jobs = self._conn.getJobs(which_jobs="all", requested_attributes=["job-state"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("getJobs fehlgeschlagen: %s", exc)
            return "unknown"

        # pycups: keys sind Job-IDs (int)
        info = jobs.get(job_id) or jobs.get(str(job_id))
        if not info:
            # Job evtl. schon aus History → completed annehmen oder unknown
            try:
                completed = self._conn.getJobs(
                    which_jobs="completed",
                    requested_attributes=["job-state"],
                )
                info = completed.get(job_id) or completed.get(str(job_id))
            except Exception:  # noqa: BLE001
                info = None
            if not info:
                return "unknown"

        state = info.get("job-state") if isinstance(info, dict) else None
        if state is None:
            return "unknown"
        try:
            return _IPP_STATE_MAP.get(int(state), "unknown")
        except (TypeError, ValueError):
            return "unknown"

    def list_queues(self) -> list[str]:
        try:
            printers = self._conn.getPrinters()
            return sorted(printers.keys())
        except Exception as exc:  # noqa: BLE001
            raise CupsUnavailable("CUPS-Queues nicht lesbar", cause=exc) from exc

    def is_available(self) -> bool:
        try:
            self._conn.getPrinters()
            return True
        except Exception:  # noqa: BLE001
            return False


def cups_available() -> bool:
    """True, wenn pycups importierbar ist (nicht zwingend CUPS-Daemon erreichbar)."""
    return _cups is not None
