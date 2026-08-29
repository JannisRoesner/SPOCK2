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
from spock2.printing.ppd_info import PpdGeometry, parse_ppd_geometry
from spock2.printing.receipt_pdf import pdf_media_size_pt

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


# Ohne diese Optionen dreht bzw. skaliert pdftopdf den Bon auf das
# Default-Medium der Queue: kurze Bons kommen um 90° gedreht quer aus der
# Rolle, lange werden auf die Seitenlänge gestaucht oder abgeschnitten.
_PDF_JOB_OPTIONS: dict[str, str] = {
    "nopdfAutoRotate": "true",  # cups-filters: Auto-Rotate in pdftopdf aus
    "orientation-requested": "3",  # IPP: portrait = nicht drehen
    "print-scaling": "none",
    "fit-to-page": "false",
    "number-up": "1",
}


def cups_media_option(data: bytes) -> str | None:
    """``Custom.<B>x<H>`` in Punkten passend zur PDF-Seite (Medium == Seite).

    Punkte statt Millimeter, weil die MediaBox selbst in Punkten steht: so
    entsteht kein Rundungsversatz, der den Filter doch noch skalieren lässt.
    """
    size = pdf_media_size_pt(data)
    if size is None:
        return None
    width_pt, height_pt = size
    return f"Custom.{round(width_pt)}x{round(height_pt)}"


def cups_job_options(data: bytes) -> dict[str, str]:
    """Job-Optionen für ``printFile``: Format plus Endlosrollen-Geometrie."""
    mime, _ = cups_payload_format(data)
    options = {"document-format": mime}
    if mime != "application/pdf":
        return options
    options.update(_PDF_JOB_OPTIONS)
    media = cups_media_option(data)
    if media:
        options["media"] = media
    return options


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
            suffix = cups_payload_format(data)[1]
            fd, tmp_path = tempfile.mkstemp(prefix="spock2_", suffix=suffix)
            try:
                os.write(fd, data)
            finally:
                os.close(fd)
            # Sichere Permissions (nur Owner)
            with contextlib.suppress(OSError):
                os.chmod(tmp_path, 0o600)
            job_id = self._print_file(queue_name, tmp_path, title or "SPOCK2", data)
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

    def _print_file(self, queue_name: str, tmp_path: str, title: str, data: bytes) -> Any:
        """``printFile`` mit Rollen-Geometrie; Fallback ohne Geometrie-Optionen.

        Queues ohne Custom-PageSize im PPD können die Optionen ablehnen – dann
        ist ein gedrehter Bon immer noch besser als kein Bon.
        """
        options = cups_job_options(data)
        try:
            logger.debug("event=cups_print_file queue=%s options=%s", queue_name, options)
            return self._conn.printFile(queue_name, tmp_path, title, options)
        except Exception as exc:  # noqa: BLE001
            minimal = {"document-format": options["document-format"]}
            if options == minimal:
                raise
            logger.warning(
                "event=cups_options_rejected queue=%s options=%s err=%s",
                queue_name,
                options,
                exc,
            )
            return self._conn.printFile(queue_name, tmp_path, title, minimal)

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

    def get_ppd_geometry(self, queue_name: str) -> PpdGeometry | None:
        """PPD-Grenzen der Queue; None bei Raw-Queues (keine PPD)."""
        tmp_path: str | None = None
        try:
            tmp_path = self._conn.getPPD(queue_name)
            if not tmp_path:
                return None
            text = Path(tmp_path).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            logger.warning("PPD für '%s' nicht lesbar: %s", queue_name, exc)
            return None
        finally:
            if tmp_path:
                with contextlib.suppress(OSError):
                    Path(tmp_path).unlink(missing_ok=True)
        return parse_ppd_geometry(text)

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
