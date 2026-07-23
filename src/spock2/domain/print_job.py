"""Druckaufträge und Status-Enums."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PrintJobStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PRINTING = "printing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    RIKER_ORDER = "riker_order"
    PICARD_NOTE = "picard_note"
    MANUAL_TEST = "manual_test"


class PrinterRole(StrEnum):
    KITCHEN = "kitchen"
    COUNTER = "counter"
    SMALL = "small"


# Erlaubte Statusübergänge (Plan §6)
ALLOWED_TRANSITIONS: dict[PrintJobStatus, frozenset[PrintJobStatus]] = {
    PrintJobStatus.PENDING: frozenset(
        {
            PrintJobStatus.SUBMITTED,
            PrintJobStatus.FAILED,
            PrintJobStatus.CANCELLED,
        }
    ),
    PrintJobStatus.SUBMITTED: frozenset(
        {
            PrintJobStatus.PRINTING,
            PrintJobStatus.COMPLETED,
            PrintJobStatus.FAILED,
            PrintJobStatus.CANCELLED,
            PrintJobStatus.UNKNOWN,
        }
    ),
    PrintJobStatus.PRINTING: frozenset(
        {
            PrintJobStatus.COMPLETED,
            PrintJobStatus.FAILED,
            PrintJobStatus.CANCELLED,
            PrintJobStatus.UNKNOWN,
        }
    ),
    PrintJobStatus.FAILED: frozenset(
        {
            PrintJobStatus.PENDING,  # Retry
            PrintJobStatus.CANCELLED,
        }
    ),
    PrintJobStatus.UNKNOWN: frozenset(
        {
            PrintJobStatus.COMPLETED,
            PrintJobStatus.FAILED,
            PrintJobStatus.CANCELLED,
            PrintJobStatus.PENDING,
        }
    ),
    PrintJobStatus.COMPLETED: frozenset(),
    PrintJobStatus.CANCELLED: frozenset(),
}


def utc_now_iso() -> str:
    """Timezone-aware UTC-Zeitstempel als ISO-8601."""
    return datetime.now(UTC).isoformat()


class PrintJob(BaseModel):
    """Persistierter Druckauftrag."""

    id: int | None = None
    source_type: SourceType
    source_id: str
    target_role: PrinterRole
    profile_name: str
    payload_json: str
    payload_hash: str
    status: PrintJobStatus = PrintJobStatus.PENDING
    attempts: int = 0
    cups_job_id: int | None = None
    last_error: str | None = None
    is_reprint: bool = False
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    completed_at: str | None = None

    @field_validator("source_id", mode="before")
    @classmethod
    def _coerce_source_id(cls, value: Any) -> str:
        return str(value)

    def can_transition_to(self, new_status: PrintJobStatus) -> bool:
        return new_status in ALLOWED_TRANSITIONS.get(self.status, frozenset())
