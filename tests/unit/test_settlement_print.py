"""Tests für RIKER-Abrechnungszettel: Enqueue, Dedup, Schema v2."""

from __future__ import annotations

import json
from pathlib import Path

from spock2.config.models import AppConfig, PrinterConfig
from spock2.domain.print_job import PrinterRole, PrintJob, PrintJobStatus, SourceType
from spock2.domain.settlements import SettlementSlip
from spock2.persistence import print_jobs, printed_sources
from spock2.persistence.db import SCHEMA_VERSION, connection, migrate
from spock2.printing.orchestrator import PrintOrchestrator
from spock2.printing.profiles.tsp100 import TSP100
from spock2.printing.renderer import ReceiptRenderer
from spock2.workers.print_worker import PrintWorker


def _cfg(**printers: PrinterConfig) -> AppConfig:
    return AppConfig(printers=dict(printers))


def _slip(slip_id: int = 9) -> SettlementSlip:
    return SettlementSlip(
        id=slip_id,
        kind="settlement",
        status="open",
        text="RIKER\nABRECHNUNG\nUmsatz bezahlt 12,50 EUR",
    )


def test_enqueue_settlement_uses_counter(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    cfg = _cfg(
        kitchen=PrinterConfig(role="kitchen", queue="Kueche", profile="tsp100"),
        counter=PrinterConfig(role="counter", queue="Theke", profile="tsp100"),
    )
    orch = PrintOrchestrator(db, cfg)
    ids = orch.enqueue_settlement(_slip())
    assert len(ids) == 1
    with connection(db) as conn:
        job = print_jobs.get_job(conn, ids[0])
        assert job is not None
        assert job.source_type == SourceType.RIKER_SETTLEMENT
        assert job.target_role == PrinterRole.COUNTER
        assert printed_sources.was_auto_enqueued(
            conn, SourceType.RIKER_SETTLEMENT, "9"
        )


def test_enqueue_settlement_falls_back_to_kitchen(tmp_path: Path) -> None:
    db = tmp_path / "fb.db"
    cfg = _cfg(
        kitchen=PrinterConfig(role="kitchen", queue="Kueche", profile="tsp100"),
        counter=PrinterConfig(role="counter", queue="", profile="tsp100"),
    )
    orch = PrintOrchestrator(db, cfg)
    ids = orch.enqueue_settlement(_slip())
    with connection(db) as conn:
        job = print_jobs.get_job(conn, ids[0])
        assert job is not None
        assert job.target_role == PrinterRole.KITCHEN


def test_enqueue_settlement_dedup(tmp_path: Path) -> None:
    db = tmp_path / "d.db"
    cfg = _cfg(
        counter=PrinterConfig(role="counter", queue="Theke", profile="tsp100"),
    )
    orch = PrintOrchestrator(db, cfg)
    first = orch.enqueue_settlement(_slip())
    second = orch.enqueue_settlement(_slip())
    assert first
    assert second == []


def test_print_worker_renders_settlement_text(tmp_path: Path) -> None:
    slip = _slip()
    job = PrintJob(
        source_type=SourceType.RIKER_SETTLEMENT,
        source_id="9",
        target_role=PrinterRole.COUNTER,
        profile_name="tsp100",
        payload_json=json.dumps(slip.model_dump(mode="json")),
        payload_hash="x",
    )
    worker = PrintWorker(
        tmp_path / "unused.db",
        AppConfig(),
        transport=None,  # type: ignore[arg-type]
        renderer=ReceiptRenderer(),
    )
    text = worker._render_payload(job, slip.model_dump(mode="json"), TSP100)
    assert "ABRECHNUNG" in text
    assert "12,50 EUR" in text


def test_migrate_v2_accepts_settlement_source(tmp_path: Path) -> None:
    db = tmp_path / "v1.db"
    # Altes v1-Schema ohne riker_settlement im CHECK
    with connection(db) as conn:
        conn.executescript(
            """
            CREATE TABLE print_jobs (
              id INTEGER PRIMARY KEY,
              source_type TEXT NOT NULL CHECK(source_type IN ('riker_order','picard_note','manual_test')),
              source_id TEXT NOT NULL,
              target_role TEXT NOT NULL CHECK(target_role IN ('kitchen','counter','small')),
              profile_name TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              payload_hash TEXT NOT NULL,
              status TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0,
              cups_job_id INTEGER,
              last_error TEXT,
              is_reprint INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              completed_at TEXT
            );
            CREATE TABLE source_ledger (
              source_type TEXT NOT NULL,
              source_id TEXT NOT NULL,
              first_seen_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              auto_enqueued INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY (source_type, source_id)
            );
            CREATE TABLE schema_migrations (
              version INTEGER PRIMARY KEY,
              applied_at TEXT NOT NULL
            );
            INSERT INTO schema_migrations(version, applied_at) VALUES (1, '2020-01-01T00:00:00+00:00');
            """
        )
    assert migrate(db) == SCHEMA_VERSION
    with connection(db) as conn:
        created = print_jobs.create_job(
            conn,
            PrintJob(
                source_type=SourceType.RIKER_SETTLEMENT,
                source_id="1",
                target_role=PrinterRole.COUNTER,
                profile_name="tsp100",
                payload_json="{}",
                payload_hash="s",
                status=PrintJobStatus.PENDING,
            ),
        )
        assert created.id is not None
        jobs = print_jobs.list_for_source(conn, SourceType.RIKER_SETTLEMENT, "1")
        assert len(jobs) == 1
