"""CRUD und Statusübergänge für print_jobs."""

from __future__ import annotations

import sqlite3
from typing import Any

from spock2.api.errors import DbError, InvalidTransitionError
from spock2.domain.print_job import (
    ALLOWED_TRANSITIONS,
    PrinterRole,
    PrintJob,
    PrintJobStatus,
    SourceType,
    utc_now_iso,
)


def _row_to_job(row: sqlite3.Row | dict[str, Any]) -> PrintJob:
    data = dict(row)
    data["is_reprint"] = bool(data.get("is_reprint"))
    return PrintJob.model_validate(data)


def create_job(conn: sqlite3.Connection, job: PrintJob) -> PrintJob:
    """Fügt einen PrintJob ein und setzt die generierte ID."""
    now = utc_now_iso()
    created = job.model_copy(
        update={
            "created_at": job.created_at or now,
            "updated_at": now,
            "status": job.status or PrintJobStatus.PENDING,
        }
    )
    try:
        cur = conn.execute(
            """
            INSERT INTO print_jobs (
              source_type, source_id, target_role, profile_name,
              payload_json, payload_hash, status, attempts, cups_job_id,
              last_error, is_reprint, created_at, updated_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created.source_type.value,
                created.source_id,
                created.target_role.value,
                created.profile_name,
                created.payload_json,
                created.payload_hash,
                created.status.value,
                created.attempts,
                created.cups_job_id,
                created.last_error,
                1 if created.is_reprint else 0,
                created.created_at,
                created.updated_at,
                created.completed_at,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise DbError(
            "Dedup: Auto-Job mit gleichem Hash existiert bereits",
            cause=exc,
        ) from exc
    except sqlite3.Error as exc:
        raise DbError("Insert print_jobs fehlgeschlagen", cause=exc) from exc

    return created.model_copy(update={"id": int(cur.lastrowid)})


def get_job(conn: sqlite3.Connection, job_id: int) -> PrintJob | None:
    row = conn.execute(
        "SELECT * FROM print_jobs WHERE id = ?", (job_id,)
    ).fetchone()
    return _row_to_job(row) if row else None


def list_jobs(
    conn: sqlite3.Connection,
    *,
    status: PrintJobStatus | None = None,
    limit: int = 100,
) -> list[PrintJob]:
    if status is None:
        rows = conn.execute(
            "SELECT * FROM print_jobs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM print_jobs WHERE status = ? ORDER BY id DESC LIMIT ?",
            (status.value, limit),
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def claim_pending(
    conn: sqlite3.Connection,
    *,
    limit: int = 1,
    retry_not_before: str | None = None,
) -> list[PrintJob]:
    """Holt pending Jobs in FIFO-Reihenfolge (für PrintWorker).

    Status bleibt ``pending`` bis Submit; Caller erhöht attempts bei Submit.

    ``retry_not_before`` (ISO-UTC) hält Retries zurück: Jobs mit ``attempts > 0``
    werden erst wieder geholt, wenn ihr ``updated_at`` älter ist. Ohne diese
    Bremse verbraucht ein defekter Drucker alle Versuche in Sekunden.
    """
    if retry_not_before is None:
        rows = conn.execute(
            """
            SELECT * FROM print_jobs
            WHERE status = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (PrintJobStatus.PENDING.value, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM print_jobs
            WHERE status = ? AND (attempts = 0 OR updated_at <= ?)
            ORDER BY id ASC
            LIMIT ?
            """,
            (PrintJobStatus.PENDING.value, retry_not_before, limit),
        ).fetchall()
    return [_row_to_job(r) for r in rows]


_UNSET: object = object()


def transition(
    conn: sqlite3.Connection,
    job_id: int,
    new_status: PrintJobStatus,
    *,
    last_error: str | None | object = _UNSET,
    cups_job_id: int | None | object = _UNSET,
    increment_attempts: bool = False,
) -> PrintJob:
    """Führt einen erlaubten Statusübergang aus."""
    job = get_job(conn, job_id)
    if job is None:
        raise DbError(f"PrintJob {job_id} nicht gefunden")

    allowed = ALLOWED_TRANSITIONS.get(job.status, frozenset())
    if new_status not in allowed:
        raise InvalidTransitionError(
            f"Übergang {job.status.value} → {new_status.value} nicht erlaubt"
        )

    now = utc_now_iso()
    completed_at = job.completed_at
    if new_status in (
        PrintJobStatus.COMPLETED,
        PrintJobStatus.CANCELLED,
        PrintJobStatus.FAILED,
    ):
        completed_at = now

    attempts = job.attempts + (1 if increment_attempts else 0)
    error: str | None = job.last_error if last_error is _UNSET else last_error  # type: ignore[assignment]
    cups_id: int | None = (
        job.cups_job_id if cups_job_id is _UNSET else cups_job_id  # type: ignore[assignment]
    )

    # Retry: failed → pending löscht completed_at / last_error
    if job.status == PrintJobStatus.FAILED and new_status == PrintJobStatus.PENDING:
        completed_at = None
        if last_error is _UNSET:
            error = None

    try:
        conn.execute(
            """
            UPDATE print_jobs
            SET status = ?, updated_at = ?, completed_at = ?,
                last_error = ?, cups_job_id = ?, attempts = ?
            WHERE id = ?
            """,
            (
                new_status.value,
                now,
                completed_at,
                error,
                cups_id,
                attempts,
                job_id,
            ),
        )
    except sqlite3.Error as exc:
        raise DbError(f"Update print_jobs #{job_id} fehlgeschlagen", cause=exc) from exc

    updated = get_job(conn, job_id)
    if updated is None:
        raise DbError(f"PrintJob {job_id} nach Update nicht gefunden")
    return updated


def mark_submitted(
    conn: sqlite3.Connection,
    job_id: int,
    cups_job_id: int,
) -> PrintJob:
    return transition(
        conn,
        job_id,
        PrintJobStatus.SUBMITTED,
        cups_job_id=cups_job_id,
        increment_attempts=True,
        last_error=None,
    )


def mark_failed(
    conn: sqlite3.Connection,
    job_id: int,
    error: str,
    *,
    increment_attempts: bool = True,
) -> PrintJob:
    return transition(
        conn,
        job_id,
        PrintJobStatus.FAILED,
        last_error=error,
        increment_attempts=increment_attempts,
    )


def requeue_failed(conn: sqlite3.Connection, job_id: int) -> PrintJob:
    """failed → pending für begrenzte Retries."""
    return transition(conn, job_id, PrintJobStatus.PENDING)


def count_by_status(conn: sqlite3.Connection, status: PrintJobStatus) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM print_jobs WHERE status = ?",
        (status.value,),
    ).fetchone()
    return int(row["c"]) if row else 0


def count_failed_since(conn: sqlite3.Connection, since_iso: str) -> int:
    """Endgültig fehlgeschlagene Jobs ab ``since_iso`` (ISO-UTC)."""
    row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM print_jobs
        WHERE status = ? AND updated_at >= ?
        """,
        (PrintJobStatus.FAILED.value, since_iso),
    ).fetchone()
    return int(row["c"]) if row else 0


def find_active_dedupe(
    conn: sqlite3.Connection,
    *,
    source_type: SourceType,
    source_id: str,
    target_role: PrinterRole,
    payload_hash: str,
) -> PrintJob | None:
    """Findet bestehenden Auto-Job mit gleichem Dedup-Schlüssel."""
    row = conn.execute(
        """
        SELECT * FROM print_jobs
        WHERE source_type = ? AND source_id = ? AND target_role = ?
          AND payload_hash = ? AND is_reprint = 0
          AND status NOT IN ('cancelled', 'failed')
        LIMIT 1
        """,
        (source_type.value, source_id, target_role.value, payload_hash),
    ).fetchone()
    return _row_to_job(row) if row else None
