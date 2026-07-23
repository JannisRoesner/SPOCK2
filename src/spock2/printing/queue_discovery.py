"""System-Drucker/Queues für Admin-UI auflisten (unabhängig vom Live-Transport)."""

from __future__ import annotations

import logging
import sys

from spock2.config.models import PrintTransportMode
from spock2.printing.cups_transport import CupsTransport, cups_available
from spock2.printing.file_transport import FileTransport
from spock2.printing.winspool_transport import WinSpoolTransport, winspool_available

logger = logging.getLogger(__name__)


def list_system_queues(mode: PrintTransportMode) -> list[str]:
    """Liefert Queue-/Druckernamen für den gewählten Transportmodus.

    Fehler beim Enumerieren führen zu einer leeren Liste (kein Raise),
    damit die Einstellungs-UI nicht abstürzt.
    """
    try:
        return _list_system_queues_unguarded(mode)
    except Exception as exc:  # noqa: BLE001
        logger.warning("event=queue_discovery_failed mode=%s err=%s", mode, exc)
        return []


def _list_system_queues_unguarded(mode: PrintTransportMode) -> list[str]:
    if mode == "file":
        return list(FileTransport().list_queues())

    if mode == "cups":
        return list(CupsTransport().list_queues())

    if mode == "winspool":
        return list(WinSpoolTransport().list_queues())

    # auto — gleiche Priorität wie create_transport
    if sys.platform.startswith("linux") and cups_available():
        try:
            return list(CupsTransport().list_queues())
        except Exception as exc:  # noqa: BLE001
            logger.warning("event=queue_discovery_cups_fallback err=%s", exc)

    if sys.platform == "win32" and winspool_available():
        try:
            return list(WinSpoolTransport().list_queues())
        except Exception as exc:  # noqa: BLE001
            logger.warning("event=queue_discovery_winspool_fallback err=%s", exc)

    return list(FileTransport().list_queues())
