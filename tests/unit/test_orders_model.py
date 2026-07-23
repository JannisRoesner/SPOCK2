"""Unit tests for Order / OrderItem pydantic models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from spock2.domain.orders import Order, OrderItem

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ORDERS_JSON = FIXTURES / "orders.json"


def test_parse_fixture_orders() -> None:
    payload = json.loads(ORDERS_JSON.read_text(encoding="utf-8"))
    orders = [Order.model_validate(row) for row in payload]
    assert len(orders) == 2
    assert orders[0].id == 42
    assert orders[0].items[0].qty == 2
    assert orders[0].items[0].notes == "ohne Zwiebeln"
    assert orders[0].is_guest is False
    assert orders[1].is_guest is True
    assert orders[1].display_table() == "Max Mustermann"


def test_order_item_qty_and_paid_coercion() -> None:
    item = OrderItem.model_validate(
        {"qty": "3", "name": "  Bier  ", "paid": 1, "price": "2.5"}
    )
    assert item.qty == 3
    assert item.name == "Bier"
    assert item.paid is True
    assert item.price == 2.5


def test_order_empty_items_default() -> None:
    order = Order.model_validate({"id": 1, "items": None})
    assert order.items == []


def test_order_requires_id() -> None:
    with pytest.raises(ValidationError):
        Order.model_validate({"table_number": 1, "items": []})


def test_display_table_fallbacks() -> None:
    assert Order(id=9, items=[]).display_table() == "#9"
    assert Order(id=9, customer_name="Gast", items=[]).display_table() == "Gast"
    assert (
        Order(id=9, table_number=3, customer_name="X", items=[]).display_table() == "3"
    )


def test_extra_riker_fields_ignored() -> None:
    order = Order.model_validate(
        {
            "id": 1,
            "table_number": 2,
            "unknown_server_field": True,
            "items": [
                {
                    "qty": 1,
                    "name": "Wasser",
                    "category_id": 99,
                    "item_id": 7,
                    "order_id": 1,
                }
            ],
        }
    )
    assert order.items[0].category_id == 99
    assert order.items[0].item_id == 7
