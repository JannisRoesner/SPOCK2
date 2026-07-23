"""Unit-Tests für print_jobs-Repository: Status + Dedup."""

from __future__ import annotations

from pathlib import Path

import pytest

from spock2.api.errors import DbError, InvalidTransitionError
from spock2.domain.print_job import PrinterRole, PrintJob, PrintJobStatus, SourceType
from spock2.persistence import print_jobs
from spock2.persistence.db import connection, migrate


def _job(
    *,
    source_id: str = "1",
    role: PrinterRole = PrinterRole.KITCHEN,
    payload_hash: str = "hash-a",
    reprint: bool = False,
) -> PrintJob:
    return PrintJob(
        source_type=SourceType.RIKER_ORDER,
        source_id=source_id,
        target_role=role,
        profile_name="tsp100",
        payload_json='{"id":1}',
        payload_hash=payload_hash,
        is_reprint=reprint,
    )


def test_status_transitions(tmp_path: Path) -> None:
    db = tmp_path / "jobs.db"
    migrate(db)
    with connection(db) as conn:
        created = print_jobs.create_job(conn, _job())
        assert created.status == PrintJobStatus.PENDING
        assert created.id is not None

        submitted = print_jobs.mark_submitted(conn, created.id, cups_job_id=10)
        assert submitted.status == PrintJobStatus.SUBMITTED
        assert submitted.attempts == 1
        assert submitted.cups_job_id == 10

        printing = print_jobs.transition(conn, created.id, PrintJobStatus.PRINTING)
        assert printing.status == PrintJobStatus.PRINTING

        done = print_jobs.transition(conn, created.id, PrintJobStatus.COMPLETED)
        assert done.status == PrintJobStatus.COMPLETED
        assert done.completed_at is not None

        with pytest.raises(InvalidTransitionError):
            print_jobs.transition(conn, created.id, PrintJobStatus.PENDING)


def test_failed_retry_cycle(tmp_path: Path) -> None:
    db = tmp_path / "retry.db"
    migrate(db)
    with connection(db) as conn:
        created = print_jobs.create_job(conn, _job())
        assert created.id is not None
        failed = print_jobs.mark_failed(conn, created.id, "boom")
        assert failed.status == PrintJobStatus.FAILED
        assert failed.attempts == 1
        assert failed.last_error == "boom"

        pending = print_jobs.requeue_failed(conn, created.id)
        assert pending.status == PrintJobStatus.PENDING
        assert pending.completed_at is None


def test_dedup_unique_index_blocks_second_auto_job(tmp_path: Path) -> None:
    db = tmp_path / "dedup.db"
    migrate(db)
    with connection(db) as conn:
        first = print_jobs.create_job(conn, _job(payload_hash="same"))
        assert first.id is not None
        with pytest.raises(DbError):
            print_jobs.create_job(conn, _job(payload_hash="same"))

        # Nachdruck erlaubt
        reprint = print_jobs.create_job(
            conn, _job(payload_hash="same", reprint=True)
        )
        assert reprint.id is not None
        assert reprint.is_reprint is True


def test_dedup_per_role(tmp_path: Path) -> None:
    db = tmp_path / "roles.db"
    migrate(db)
    with connection(db) as conn:
        a = print_jobs.create_job(
            conn, _job(role=PrinterRole.KITCHEN, payload_hash="h")
        )
        b = print_jobs.create_job(
            conn, _job(role=PrinterRole.COUNTER, payload_hash="h")
        )
        assert a.id != b.id


def test_find_active_dedupe(tmp_path: Path) -> None:
    db = tmp_path / "find.db"
    migrate(db)
    with connection(db) as conn:
        created = print_jobs.create_job(conn, _job(payload_hash="xyz"))
        found = print_jobs.find_active_dedupe(
            conn,
            source_type=SourceType.RIKER_ORDER,
            source_id="1",
            target_role=PrinterRole.KITCHEN,
            payload_hash="xyz",
        )
        assert found is not None
        assert found.id == created.id

        print_jobs.mark_failed(conn, created.id, "x")
        # failed ist nicht mehr „aktiv“ im Dedup-Index
        found2 = print_jobs.find_active_dedupe(
            conn,
            source_type=SourceType.RIKER_ORDER,
            source_id="1",
            target_role=PrinterRole.KITCHEN,
            payload_hash="xyz",
        )
        assert found2 is None


def test_claim_pending_fifo(tmp_path: Path) -> None:
    db = tmp_path / "fifo.db"
    migrate(db)
    with connection(db) as conn:
        j1 = print_jobs.create_job(conn, _job(source_id="1", payload_hash="a"))
        j2 = print_jobs.create_job(conn, _job(source_id="2", payload_hash="b"))
        claimed = print_jobs.claim_pending(conn, limit=2)
        assert [c.id for c in claimed] == [j1.id, j2.id]
