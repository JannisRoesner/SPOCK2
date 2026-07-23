"""Print-Orchestrator: Enqueue, Dedup, Ledger."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from spock2.api.errors import DbError
from spock2.config.models import AppConfig
from spock2.domain.notes import Note
from spock2.domain.orders import Order
from spock2.domain.print_job import PrinterRole, PrintJob, SourceType
from spock2.persistence import print_jobs, printed_sources
from spock2.persistence.db import connection, migrate
from spock2.printing.profiles import get_profile
from spock2.printing.renderer import ReceiptRenderer
from spock2.printing.routing import (
    items_for_role,
    resolve_role_for_note,
    resolve_roles_for_order,
)
from spock2.printing.transport import PrintTransport

logger = logging.getLogger(__name__)


def canonical_json(payload: dict[str, Any]) -> str:
    """Stabile JSON-Serialisierung für Hashing (sortierte Keys, UTF-8)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(payload: dict[str, Any]) -> str:
    """SHA-256 über kanonisches JSON."""
    raw = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def order_payload(
    order: Order,
    role: PrinterRole,
    routing_items: list | None = None,
) -> dict[str, Any]:
    """Kanonisches Payload für Order-Jobs (inkl. gefilterter Items)."""
    data = order.model_dump(mode="json")
    if routing_items is not None:
        data["items"] = [
            i.model_dump(mode="json") if hasattr(i, "model_dump") else i
            for i in routing_items
        ]
    data["_target_role"] = role.value
    return data


def note_payload(note: Note, role: PrinterRole) -> dict[str, Any]:
    data = note.model_dump(mode="json")
    data["_target_role"] = role.value
    return data


class PrintOrchestrator:
    """Erzeugt PrintJobs in SQLite; Dedup über Hash + Ledger.

    ``auto_print_*``-Flags werden bewusst **nicht** geprüft — das ist
    Sache der Service-Schicht. Der Orchestrator enqueued immer, wenn gerufen.
    """

    def __init__(
        self,
        db_path: str | Path,
        config: AppConfig,
        transport: PrintTransport | None = None,
        renderer: ReceiptRenderer | None = None,
        *,
        ensure_schema: bool = True,
    ) -> None:
        self.db_path = Path(db_path)
        self.config = config
        self.transport = transport
        self.renderer = renderer or ReceiptRenderer()
        if ensure_schema:
            migrate(self.db_path)

    def enqueue_order(self, order: Order, *, reprint: bool = False) -> list[int]:
        """Enqueued einen oder mehrere Jobs (eine Rolle → ein Job)."""
        roles = resolve_roles_for_order(order, self.config.routing)
        job_ids: list[int] = []

        with connection(self.db_path) as conn:
            if not reprint and printed_sources.was_auto_enqueued(
                conn, SourceType.RIKER_ORDER, str(order.id)
            ):
                logger.debug(
                    "Order %s bereits auto_enqueued – übersprungen", order.id
                )
                return []

            for role in roles:
                filtered = items_for_role(order, role, self.config.routing)
                payload = order_payload(order, role, filtered)
                phash = payload_hash(payload)

                if not reprint:
                    existing = print_jobs.find_active_dedupe(
                        conn,
                        source_type=SourceType.RIKER_ORDER,
                        source_id=str(order.id),
                        target_role=role,
                        payload_hash=phash,
                    )
                    if existing is not None:
                        if existing.id is not None:
                            job_ids.append(existing.id)
                        continue

                profile_name = self._profile_for_role(role)
                job = PrintJob(
                    source_type=SourceType.RIKER_ORDER,
                    source_id=str(order.id),
                    target_role=role,
                    profile_name=profile_name,
                    payload_json=canonical_json(payload),
                    payload_hash=phash,
                    is_reprint=reprint,
                )
                try:
                    created = print_jobs.create_job(conn, job)
                except DbError as exc:
                    logger.info(
                        "Dedup-Konflikt Order %s Rolle %s: %s",
                        order.id,
                        role.value,
                        exc.message,
                    )
                    existing = print_jobs.find_active_dedupe(
                        conn,
                        source_type=SourceType.RIKER_ORDER,
                        source_id=str(order.id),
                        target_role=role,
                        payload_hash=phash,
                    )
                    if existing and existing.id is not None:
                        job_ids.append(existing.id)
                    continue
                if created.id is not None:
                    job_ids.append(created.id)

            if not reprint:
                printed_sources.mark_auto_enqueued(
                    conn, SourceType.RIKER_ORDER, str(order.id)
                )

        return job_ids

    def enqueue_note(self, note: Note, *, reprint: bool = False) -> list[int]:
        """Enqueued einen Zettel-Job an die Stationsrolle."""
        role = resolve_role_for_note(self.config.routing)
        payload = note_payload(note, role)
        phash = payload_hash(payload)
        job_ids: list[int] = []

        with connection(self.db_path) as conn:
            if not reprint and printed_sources.was_auto_enqueued(
                conn, SourceType.PICARD_NOTE, note.id
            ):
                return []

            if not reprint:
                existing = print_jobs.find_active_dedupe(
                    conn,
                    source_type=SourceType.PICARD_NOTE,
                    source_id=note.id,
                    target_role=role,
                    payload_hash=phash,
                )
                if existing is not None:
                    printed_sources.mark_auto_enqueued(
                        conn, SourceType.PICARD_NOTE, note.id
                    )
                    return [existing.id] if existing.id is not None else []

            profile_name = self._profile_for_role(role)
            job = PrintJob(
                source_type=SourceType.PICARD_NOTE,
                source_id=note.id,
                target_role=role,
                profile_name=profile_name,
                payload_json=canonical_json(payload),
                payload_hash=phash,
                is_reprint=reprint,
            )
            try:
                created = print_jobs.create_job(conn, job)
            except DbError:
                printed_sources.mark_auto_enqueued(
                    conn, SourceType.PICARD_NOTE, note.id
                )
                return []
            if created.id is not None:
                job_ids.append(created.id)
            if not reprint:
                printed_sources.mark_auto_enqueued(
                    conn, SourceType.PICARD_NOTE, note.id
                )

        return job_ids

    def enqueue_test(self, role: PrinterRole | str) -> list[int]:
        """Testseite für eine Rolle (immer neuer Job, is_reprint=False aber unique source_id)."""
        target = PrinterRole(role) if isinstance(role, str) else role
        profile_name = self._profile_for_role(target)
        profile = get_profile(profile_name)
        text = self.renderer.format_test(target, profile)
        payload: dict[str, Any] = {
            "kind": "manual_test",
            "role": target.value,
            "profile": profile_name,
            "text": text,
        }
        # Eindeutige source_id pro Aufruf (Zeit-Hash), damit Dedup nicht greift
        phash = payload_hash(payload)
        source_id = f"test-{target.value}-{phash[:12]}"

        with connection(self.db_path) as conn:
            job = PrintJob(
                source_type=SourceType.MANUAL_TEST,
                source_id=source_id,
                target_role=target,
                profile_name=profile_name,
                payload_json=canonical_json(payload),
                payload_hash=phash,
                is_reprint=False,
            )
            try:
                created = print_jobs.create_job(conn, job)
            except DbError:
                # Gleicher Testinhalt schon pending → bestehende ID
                existing = print_jobs.find_active_dedupe(
                    conn,
                    source_type=SourceType.MANUAL_TEST,
                    source_id=source_id,
                    target_role=target,
                    payload_hash=phash,
                )
                return [existing.id] if existing and existing.id is not None else []
            return [created.id] if created.id is not None else []

    def _profile_for_role(self, role: PrinterRole) -> str:
        printer = self.config.printer_for_role(role.value)  # type: ignore[arg-type]
        if printer is not None:
            return printer.profile
        # Fallback aus profiles-Dict / Builtin
        if role == PrinterRole.SMALL:
            return "pos5890k"
        return "tsp100"
