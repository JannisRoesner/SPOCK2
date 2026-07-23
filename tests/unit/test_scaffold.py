"""Basis-Tests für Scaffold (Config, Domain, Persistenz)."""

from __future__ import annotations

from pathlib import Path

from spock2.config.loader import load_config
from spock2.config.models import AppConfig
from spock2.domain.orders import Order, OrderItem
from spock2.domain.print_job import PrinterRole, PrintJob, PrintJobStatus, SourceType
from spock2.persistence import print_jobs, printed_sources
from spock2.persistence.db import connection as db_connection
from spock2.persistence.db import migrate


def test_app_config_defaults() -> None:
    cfg = AppConfig()
    assert cfg.riker.base_url.startswith("http")
    assert cfg.polling.interval_s > 0
    assert cfg.print.auto_complete_after_print is False


def test_load_example_toml() -> None:
    example = Path(__file__).resolve().parents[2] / "config" / "spock2.example.toml"
    cfg = load_config(example, allow_missing=False)
    assert "kitchen" in cfg.printers or any(
        p.role == "kitchen" for p in cfg.printers.values()
    )
    assert cfg.routing.station_role in ("kitchen", "counter")
    assert cfg.profiles["tsp100"].paper_width_mm == 80


def test_order_model() -> None:
    order = Order(
        id=1,
        table_number=5,
        items=[OrderItem(qty=2, name="Schnitzel", category="Speisen")],
    )
    assert order.display_table() == "5"
    assert len(order.items) == 1


def test_print_job_persist_and_claim(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrate(db_path)

    job = PrintJob(
        source_type=SourceType.RIKER_ORDER,
        source_id="42",
        target_role=PrinterRole.KITCHEN,
        profile_name="tsp100",
        payload_json='{"id":42}',
        payload_hash="abc123",
    )

    with db_connection(db_path) as conn:
        created = print_jobs.create_job(conn, job)
        assert created.id is not None
        claimed = print_jobs.claim_pending(conn, limit=1)
        assert len(claimed) == 1
        assert claimed[0].id == created.id

        submitted = print_jobs.mark_submitted(conn, created.id, cups_job_id=99)
        assert submitted.status == PrintJobStatus.SUBMITTED
        assert submitted.cups_job_id == 99
        assert submitted.attempts == 1

        completed = print_jobs.transition(
            conn, created.id, PrintJobStatus.COMPLETED
        )
        assert completed.status == PrintJobStatus.COMPLETED
        assert completed.completed_at is not None


def test_source_ledger(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.db"
    migrate(db_path)

    with db_connection(db_path) as conn:
        assert not printed_sources.was_auto_enqueued(
            conn, SourceType.RIKER_ORDER, "7"
        )
        printed_sources.mark_auto_enqueued(conn, SourceType.RIKER_ORDER, "7")
        assert printed_sources.was_auto_enqueued(conn, SourceType.RIKER_ORDER, "7")
        entry = printed_sources.get_entry(conn, SourceType.RIKER_ORDER, "7")
        assert entry is not None
        assert entry["auto_enqueued"] is True
