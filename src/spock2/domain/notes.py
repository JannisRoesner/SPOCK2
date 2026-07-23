"""Domain-Modell für PICARD-Zettel."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class Note(BaseModel):
    """PICARD-Zettel (tolerant gegenüber Feldvarianten)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    text: str = ""
    type: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "type",
            "typ",
            "target",
            "recipient",
            "empfaenger",
            "empfänger",
        ),
    )
    priority: int | str | None = None
    sender: str | None = None
    timestamp: datetime | str | None = None
    closed: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "closed",
            "geschlossen",
            "isClosed",
            "is_closed",
        ),
    )

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, value: Any) -> str:
        return str(value)

    @field_validator("text", mode="before")
    @classmethod
    def _default_text(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    @field_validator("closed", mode="before")
    @classmethod
    def _coerce_closed(cls, value: Any) -> bool:
        if value in (None, "", 0, "0", "false", "False"):
            return False
        if value in (1, "1", "true", "True"):
            return True
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"yes", "ja", "closed", "geschlossen"}:
                return True
            if normalized in {"no", "nein", "open", "offen"}:
                return False
        return bool(value)

    @model_validator(mode="before")
    @classmethod
    def _status_as_closed(cls, data: Any) -> Any:
        """Map status-like fields when explicit closed flags are absent."""
        if not isinstance(data, dict):
            return data
        has_closed = any(
            k in data
            for k in ("closed", "geschlossen", "isClosed", "is_closed")
        )
        if has_closed:
            return data
        status = data.get("status")
        if isinstance(status, str):
            normalized = status.strip().casefold()
            if normalized in {"closed", "geschlossen", "1", "true"}:
                data = {**data, "closed": True}
            elif normalized in {"open", "offen", "0", "false"}:
                data = {**data, "closed": False}
        return data

    def is_kitchen_target(self, kitchen_types: list[str]) -> bool:
        """Prüft, ob der Zettel-Typ als Küchen-Ziel gilt."""
        if not self.type:
            return False
        normalized = self.type.strip().casefold().replace(" ", "").replace("-", "_")
        for candidate in kitchen_types:
            cand = candidate.strip().casefold().replace(" ", "").replace("-", "_")
            if normalized == cand:
                return True
        return False
