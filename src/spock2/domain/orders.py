"""Domain-Modelle für RIKER-Bestellungen."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderItem(BaseModel):
    """Einzelposition einer Bestellung (RIKER order_items + join)."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    qty: int = Field(ge=0)
    name: str
    notes: str | None = None
    category: str | None = None
    category_id: int | None = None
    price: float | None = None
    paid: bool | None = None
    item_id: int | None = None
    order_id: int | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("qty", mode="before")
    @classmethod
    def _coerce_qty(cls, value: Any) -> Any:
        if value is None or value == "":
            return 0
        return value

    @field_validator("paid", mode="before")
    @classmethod
    def _coerce_paid(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        if value in (0, "0", "false", "False", False):
            return False
        if value in (1, "1", "true", "True", True):
            return True
        return value

    @field_validator("notes", mode="before")
    @classmethod
    def _empty_notes(cls, value: Any) -> Any:
        if value == "":
            return None
        return value


class Order(BaseModel):
    """Offene RIKER-Bestellung."""

    model_config = ConfigDict(extra="ignore")

    id: int
    table_number: str | int | None = None
    waiter: str | None = None
    total: float | None = None
    status: str = "open"
    created_at: datetime | str | None = None
    is_guest: bool | None = None
    customer_name: str | None = None
    items: list[OrderItem] = Field(default_factory=list)

    @field_validator("items", mode="before")
    @classmethod
    def _default_items(cls, value: Any) -> Any:
        return value if value is not None else []

    @field_validator("is_guest", mode="before")
    @classmethod
    def _coerce_guest(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        if value in (0, "0", "false", "False", False):
            return False
        if value in (1, "1", "true", "True", True):
            return True
        return value

    def display_table(self) -> str:
        """Lesbare Tisch-/Gastbezeichnung."""
        if self.is_guest and self.customer_name:
            return str(self.customer_name)
        if self.table_number is not None:
            return str(self.table_number)
        if self.customer_name:
            return str(self.customer_name)
        return f"#{self.id}"
