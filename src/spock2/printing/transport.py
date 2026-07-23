"""Druck-Transport-Protokoll."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PrintTransport(Protocol):
    """Abstraktion über CUPS / File-Dev-Transport."""

    def submit(self, queue_name: str, data: bytes, title: str) -> int | None:
        """Reicht Bytes an die Queue; gibt Job-ID oder None zurück."""
        ...

    def get_job_state(self, job_id: int) -> str:
        """Liefert einen transport-spezifischen Status-String."""
        ...

    def list_queues(self) -> list[str]:
        """Bekannte Queue-Namen."""
        ...

    def is_available(self) -> bool:
        """True, wenn der Transport nutzbar ist."""
        ...
