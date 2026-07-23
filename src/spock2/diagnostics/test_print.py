"""Testprint-CLI je Druckerrolle."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from spock2.config.loader import load_config
from spock2.domain.print_job import PrinterRole, PrintJobStatus
from spock2.persistence import print_jobs
from spock2.persistence.db import connection, migrate
from spock2.printing.cups_transport import CupsTransport, cups_available
from spock2.printing.file_transport import FileTransport
from spock2.printing.orchestrator import PrintOrchestrator
from spock2.printing.profiles import get_profile
from spock2.printing.renderer import ReceiptRenderer
from spock2.printing.winspool_transport import WinSpoolTransport, winspool_available
from spock2.workers.print_worker import PrintWorker


def _build_transport(prefer_file: bool, file_out: str | None):
    if prefer_file:
        return FileTransport(file_out), "file"
    if cups_available():
        try:
            return CupsTransport(), "cups"
        except Exception as exc:  # noqa: BLE001
            print(f"CUPS nicht nutzbar ({exc}) – Fallback weiter.", file=sys.stderr)
    if winspool_available():
        try:
            return WinSpoolTransport(), "winspool"
        except Exception as exc:  # noqa: BLE001
            print(f"WinSpool nicht nutzbar ({exc}) – Fallback FileTransport.", file=sys.stderr)
    return FileTransport(file_out), "file"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="spock2-test-print",
        description="Sendet eine Testseite an eine Rollenqueue (CUPS oder FileTransport).",
    )
    parser.add_argument(
        "--role",
        choices=["kitchen", "counter", "small"],
        default="kitchen",
        help="Druckerrolle (Default: kitchen)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Pfad zur TOML-Config (sonst SPOCK2_CONFIG / Defaults)",
    )
    parser.add_argument(
        "--file",
        action="store_true",
        help="Erzwinge FileTransport (Dev/Windows)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Ausgabeordner für FileTransport (sonst SPOCK2_PRINT_OUT / Default)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur Bon-Text auf stdout, kein Submit",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="SQLite-Pfad (Default: aus Config / Temp unter State-Dir)",
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config, allow_missing=True)
    role = PrinterRole(args.role)
    printer = cfg.printer_for_role(role.value)  # type: ignore[arg-type]
    profile_name = printer.profile if printer else (
        "pos5890k" if role == PrinterRole.SMALL else "tsp100"
    )
    profile = get_profile(profile_name)
    renderer = ReceiptRenderer()
    text = renderer.format_test(role, profile)

    print("--- Testbon ---")
    print(text)
    print("---------------")

    if args.dry_run:
        return 0

    transport, kind = _build_transport(args.file, args.out)
    print(f"Transport: {kind}  available={transport.is_available()}")
    if kind == "file" and isinstance(transport, FileTransport):
        print(f"Ausgabe: {transport.output_dir}")
    if printer:
        print(f"Queue: {printer.queue}  Profil: {profile_name}")
    else:
        print(f"Kein Printer-Config für Rolle {role.value} – Fallback-Queue spock-{role.value}")

    db_path = Path(args.db) if args.db else cfg.db.resolved_path()
    migrate(db_path)
    orch = PrintOrchestrator(db_path, cfg, transport=transport, renderer=renderer)
    ids = orch.enqueue_test(role)
    if not ids:
        print("Kein Job erzeugt.", file=sys.stderr)
        return 1
    print(f"Enqueued Job-IDs: {ids}")

    worker = PrintWorker(db_path, cfg, transport, renderer)
    n = worker.process_once(limit=max(len(ids), 1))
    print(f"Verarbeitet: {n}")

    with connection(db_path) as conn:
        for jid in ids:
            job = print_jobs.get_job(conn, jid)
            if job is None:
                continue
            print(
                f"  job#{job.id} status={job.status.value} "
                f"cups_id={job.cups_job_id} attempts={job.attempts} "
                f"err={job.last_error!r}"
            )
            if job.status not in (
                PrintJobStatus.SUBMITTED,
                PrintJobStatus.PRINTING,
                PrintJobStatus.COMPLETED,
            ):
                return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
