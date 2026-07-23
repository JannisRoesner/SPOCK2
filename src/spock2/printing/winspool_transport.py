"""Windows-Spooler-Transport (RAW / ESC/POS) via pywin32."""

from __future__ import annotations

import contextlib
import logging
import sys
from typing import Any

from spock2.api.errors import CupsUnavailable, PrintFailed

logger = logging.getLogger(__name__)

_win32print: Any | None
_WIN32_IMPORT_ERROR: BaseException | None

if sys.platform == "win32":
    try:
        import win32print as _win32print_mod  # type: ignore[import-untyped]

        _win32print = _win32print_mod
        _WIN32_IMPORT_ERROR = None
    except Exception as exc:  # noqa: BLE001
        _win32print = None
        _WIN32_IMPORT_ERROR = exc
else:
    _win32print = None
    _WIN32_IMPORT_ERROR = None

# JOB_STATUS_* Bitflags (winspool.h)
_JOB_STATUS_PAUSED = 0x00000001
_JOB_STATUS_ERROR = 0x00000002
_JOB_STATUS_DELETING = 0x00000004
_JOB_STATUS_SPOOLING = 0x00000008
_JOB_STATUS_PRINTING = 0x00000010
_JOB_STATUS_OFFLINE = 0x00000020
_JOB_STATUS_PAPEROUT = 0x00000040
_JOB_STATUS_PRINTED = 0x00000080
_JOB_STATUS_DELETED = 0x00000100
_JOB_STATUS_BLOCKED_DEVQ = 0x00000200
_JOB_STATUS_USER_INTERVENTION = 0x00000400


def _map_job_status(status_flags: int) -> str:
    if status_flags & (
        _JOB_STATUS_ERROR
        | _JOB_STATUS_PAPEROUT
        | _JOB_STATUS_OFFLINE
        | _JOB_STATUS_USER_INTERVENTION
        | _JOB_STATUS_BLOCKED_DEVQ
    ):
        return "failed"
    if status_flags & (_JOB_STATUS_DELETING | _JOB_STATUS_DELETED):
        return "cancelled"
    if status_flags & _JOB_STATUS_PRINTING:
        return "printing"
    if status_flags & _JOB_STATUS_PRINTED:
        return "completed"
    if status_flags & (_JOB_STATUS_SPOOLING | _JOB_STATUS_PAUSED):
        return "pending"
    return "pending"


class WinSpoolTransport:
    """pywin32 RAW-Submit an Windows-Druckernamen."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise CupsUnavailable("WinSpool nur unter Windows verfügbar")
        if _win32print is None:
            raise CupsUnavailable(
                "pywin32/win32print nicht verfügbar",
                cause=_WIN32_IMPORT_ERROR,
            )
        self._wp = _win32print
        self._job_printers: dict[int, str] = {}

    def submit(self, queue_name: str, data: bytes, title: str) -> int | None:
        if not queue_name:
            raise PrintFailed("Leerer Druckername")
        try:
            handle = self._wp.OpenPrinter(queue_name)
        except Exception as exc:  # noqa: BLE001
            raise PrintFailed(
                f"Drucker '{queue_name}' nicht öffenbar",
                cause=exc,
            ) from exc

        job_id: int | None = None
        try:
            doc_name = title or "SPOCK2"
            job_id = int(
                self._wp.StartDocPrinter(handle, 1, (doc_name, None, "RAW"))
            )
            self._wp.StartPagePrinter(handle)
            written = self._wp.WritePrinter(handle, data)
            if not written and data:
                raise PrintFailed(
                    f"WritePrinter an '{queue_name}' schrieb 0 Bytes"
                )
            self._wp.EndPagePrinter(handle)
            self._wp.EndDocPrinter(handle)
        except PrintFailed:
            raise
        except Exception as exc:  # noqa: BLE001
            raise PrintFailed(
                f"WinSpool-Submit an '{queue_name}' fehlgeschlagen",
                cause=exc,
            ) from exc
        finally:
            try:
                self._wp.ClosePrinter(handle)
            except Exception:  # noqa: BLE001
                logger.warning("ClosePrinter fehlgeschlagen für %s", queue_name)

        if job_id:
            self._job_printers[job_id] = queue_name
            return job_id
        return None

    def get_job_state(self, job_id: int) -> str:
        printer = self._job_printers.get(job_id)
        candidates = [printer] if printer else self.list_queues()
        for name in candidates:
            if not name:
                continue
            try:
                handle = self._wp.OpenPrinter(name)
            except Exception:  # noqa: BLE001
                continue
            try:
                jobs = self._wp.EnumJobs(handle, 0, -1, 1)
            except Exception as exc:  # noqa: BLE001
                logger.warning("EnumJobs fehlgeschlagen (%s): %s", name, exc)
                jobs = []
            finally:
                with contextlib.suppress(Exception):
                    self._wp.ClosePrinter(handle)

            for job in jobs or []:
                jid = job.get("JobId") if isinstance(job, dict) else None
                if jid is None and hasattr(job, "JobId"):
                    jid = job.JobId
                if int(jid or 0) != int(job_id):
                    continue
                status = 0
                if isinstance(job, dict):
                    status = int(job.get("Status") or 0)
                elif hasattr(job, "Status"):
                    status = int(job.Status)
                return _map_job_status(status)

        # Job nicht mehr in der Queue → als completed annehmen
        if printer is not None:
            return "completed"
        return "unknown"

    def list_queues(self) -> list[str]:
        try:
            flags = self._wp.PRINTER_ENUM_LOCAL | self._wp.PRINTER_ENUM_CONNECTIONS
            printers = self._wp.EnumPrinters(flags)
        except Exception as exc:  # noqa: BLE001
            raise CupsUnavailable("Windows-Drucker nicht lesbar", cause=exc) from exc

        names: list[str] = []
        for entry in printers or []:
            # EnumPrinters level 2 / default: (flags, desc, name, comment) or dict
            if isinstance(entry, dict):
                name = entry.get("pPrinterName") or entry.get("PrinterName")
            elif isinstance(entry, (tuple, list)) and len(entry) >= 3:
                name = entry[2]
            else:
                name = None
            if name:
                names.append(str(name))
        return sorted(set(names))

    def is_available(self) -> bool:
        try:
            return len(self.list_queues()) > 0
        except Exception:  # noqa: BLE001
            return False


def winspool_available() -> bool:
    """True, wenn unter Windows und win32print importierbar ist."""
    return sys.platform == "win32" and _win32print is not None
