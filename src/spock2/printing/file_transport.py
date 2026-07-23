"""Datei-Transport für Windows/Dev (kein CUPS nötig)."""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime
from pathlib import Path


class FileTransport:
    """Schreibt Bon-Bytes in ein Verzeichnis; Fake-Job-IDs.

    Pfad: Konstruktor-Argument oder Umgebungsvariable ``SPOCK2_PRINT_OUT``.
    Default: ``%LOCALAPPDATA%/spock2/out`` (Windows) bzw. ``~/.local/state/spock2/out``.
    """

    ENV_OUT = "SPOCK2_PRINT_OUT"

    def __init__(self, output_dir: str | Path | None = None) -> None:
        if output_dir is not None:
            self.output_dir = Path(output_dir).expanduser()
        else:
            env = os.environ.get(self.ENV_OUT)
            if env:
                self.output_dir = Path(env).expanduser()
            else:
                local = os.environ.get("LOCALAPPDATA")
                if local:
                    self.output_dir = Path(local) / "spock2" / "out"
                else:
                    self.output_dir = (
                        Path.home() / ".local" / "state" / "spock2" / "out"
                    )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._next_id = 1
        self._jobs: dict[int, str] = {}

    def submit(self, queue_name: str, data: bytes, title: str) -> int | None:
        safe_queue = "".join(c if c.isalnum() or c in "-_" else "_" for c in queue_name)
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:64]
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        with self._lock:
            job_id = self._next_id
            self._next_id += 1
            self._jobs[job_id] = "completed"
        filename = f"{ts}_{safe_queue}_{job_id}_{safe_title or 'job'}.txt"
        path = self.output_dir / filename
        path.write_bytes(data)
        # Begleit-Meta
        meta = path.with_suffix(".meta")
        meta.write_text(
            f"queue={queue_name}\njob_id={job_id}\ntitle={title}\nbytes={len(data)}\n",
            encoding="utf-8",
        )
        return job_id

    def get_job_state(self, job_id: int) -> str:
        with self._lock:
            # Sofort completed (Dev-Semantik)
            if job_id in self._jobs:
                return "completed"
            return "completed"

    def list_queues(self) -> list[str]:
        return ["file-kitchen", "file-counter", "file-small"]

    def is_available(self) -> bool:
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            return self.output_dir.is_dir() and os.access(self.output_dir, os.W_OK)
        except OSError:
            return False
