"""Integration: Enqueue → Restart → keine doppelten Auto-Jobs."""

from __future__ import annotations

from pathlib import Path

from spock2.config.models import AppConfig, PrinterConfig, RoutingConfig
from spock2.domain.orders import Order, OrderItem
from spock2.domain.print_job import PrinterRole, PrintJobStatus, SourceType
from spock2.persistence import print_jobs, printed_sources
from spock2.persistence.db import connection, migrate
from spock2.printing.file_transport import FileTransport
from spock2.printing.orchestrator import PrintOrchestrator
from spock2.printing.renderer import ReceiptRenderer


def _config() -> AppConfig:
    return AppConfig(
        printers={
            "kitchen": PrinterConfig(
                role="kitchen",
                cups_queue="spock-kitchen",
                profile="tsp100",
            ),
            "counter": PrinterConfig(
                role="counter",
                cups_queue="spock-counter",
                profile="tsp100",
            ),
        },
        routing=RoutingConfig(
            station_role="kitchen",
            category_routing={
                "Getränke": ["counter"],
                "Speisen": ["kitchen"],
            },
        ),
    )


def test_enqueue_restart_no_duplicate_auto_jobs(tmp_path: Path) -> None:
    db = tmp_path / "queue.db"
    out = tmp_path / "out"
    migrate(db)
    cfg = _config()
    transport = FileTransport(out)
    renderer = ReceiptRenderer()

    order = Order(
        id=42,
        table_number=7,
        waiter="Ada",
        items=[
            OrderItem(qty=1, name="Schnitzel", category="Speisen"),
            OrderItem(qty=2, name="Cola", category="Getränke"),
        ],
    )

    orch1 = PrintOrchestrator(db, cfg, transport=transport, renderer=renderer)
    ids1 = orch1.enqueue_order(order, reprint=False)
    assert len(ids1) == 2  # kitchen + counter
    assert sorted(ids1) == sorted(set(ids1))

    with connection(db) as conn:
        assert printed_sources.was_auto_enqueued(conn, SourceType.RIKER_ORDER, "42")
        pending = print_jobs.count_by_status(conn, PrintJobStatus.PENDING)
        assert pending == 2

    # „Restart“: neuer Orchestrator, gleiche DB
    orch2 = PrintOrchestrator(db, cfg, transport=transport, renderer=renderer)
    ids2 = orch2.enqueue_order(order, reprint=False)
    assert ids2 == []

    with connection(db) as conn:
        all_jobs = print_jobs.list_jobs(conn, limit=50)
        auto_jobs = [j for j in all_jobs if not j.is_reprint]
        assert len(auto_jobs) == 2

    # Nachdruck erzeugt neue Jobs
    ids3 = orch2.enqueue_order(order, reprint=True)
    assert len(ids3) == 2
    with connection(db) as conn:
        all_jobs = print_jobs.list_jobs(conn, limit=50)
        reprints = [j for j in all_jobs if j.is_reprint]
        assert len(reprints) == 2
        assert all(j.target_role in (PrinterRole.KITCHEN, PrinterRole.COUNTER) for j in reprints)
