"""Domain-Modell für RIKER-Abrechnungszettel."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SettlementSlip(BaseModel):
    """Offener Thermal-Abrechnungszettel aus ``GET /api/settlements``."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: int
    kind: str = "settlement"
    status: str = "open"
    text: str = ""
    created_at: datetime | str | None = Field(
        default=None,
        validation_alias="created_at",
    )

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, value: Any) -> int:
        return int(value)

    @field_validator("text", mode="before")
    @classmethod
    def _default_text(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @field_validator("status", mode="before")
    @classmethod
    def _default_status(cls, value: Any) -> str:
        if value is None or value == "":
            return "open"
        return str(value)

    def is_open(self) -> bool:
        return self.status.strip().casefold() in {"", "open", "offen"}
