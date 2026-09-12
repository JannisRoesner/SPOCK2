"""Unit-Tests für Druck-Routing."""

from __future__ import annotations

from spock2.config.models import AppConfig, PrinterConfig, RoutingConfig
from spock2.domain.orders import Order, OrderItem
from spock2.domain.print_job import PrinterRole
from spock2.printing.routing import (
    items_for_role,
    resolve_role_for_note,
    resolve_role_for_settlement,
    resolve_roles_for_order,
)


def test_station_role_default_when_no_rules() -> None:
    order = Order(
        id=1,
        items=[OrderItem(qty=1, name="Cola", category="Getränke")],
    )
    routing = RoutingConfig(station_role="counter", category_routing={})
    assert resolve_roles_for_order(order, routing) == [PrinterRole.COUNTER]


def test_station_fallback_when_categories_unmatched() -> None:
    order = Order(
        id=1,
        items=[OrderItem(qty=1, name="Snack", category="Unbekannt")],
    )
    routing = RoutingConfig(
        station_role="kitchen",
        category_routing={"Getränke": ["counter"]},
    )
    assert resolve_roles_for_order(order, routing) == [PrinterRole.KITCHEN]


def test_category_routing_collects_unique_roles() -> None:
    order = Order(
        id=2,
        items=[
            OrderItem(qty=1, name="Bier", category="Getränke"),
            OrderItem(qty=1, name="Schnitzel", category="Speisen"),
            OrderItem(qty=1, name="Cola", category="Getränke"),
        ],
    )
    routing = RoutingConfig(
        station_role="kitchen",
        category_routing={
            "Getränke": ["counter"],
            "Speisen": ["kitchen"],
            "Dessert": ["kitchen"],
        },
    )
    roles = resolve_roles_for_order(order, routing)
    assert roles == [PrinterRole.COUNTER, PrinterRole.KITCHEN]


def test_category_routing_case_insensitive() -> None:
    order = Order(
        id=3,
        items=[OrderItem(qty=1, name="Wasser", category="getränke")],
    )
    routing = RoutingConfig(
        station_role="kitchen",
        category_routing={"Getränke": ["counter"]},
    )
    assert resolve_roles_for_order(order, routing) == [PrinterRole.COUNTER]


def test_multi_role_category() -> None:
    order = Order(
        id=4,
        items=[OrderItem(qty=1, name="Menü", category="Sonstiges")],
    )
    routing = RoutingConfig(
        station_role="kitchen",
        category_routing={"Sonstiges": ["kitchen", "counter"]},
    )
    assert resolve_roles_for_order(order, routing) == [
        PrinterRole.KITCHEN,
        PrinterRole.COUNTER,
    ]


def test_note_uses_station_role() -> None:
    routing = RoutingConfig(station_role="counter")
    assert resolve_role_for_note(routing) == PrinterRole.COUNTER


def test_settlement_prefers_counter_printer() -> None:
    cfg = AppConfig(
        printers={
            "kitchen": PrinterConfig(
                role="kitchen", queue="spock-kitchen", profile="tsp100"
            ),
            "counter": PrinterConfig(
                role="counter", queue="Theke", profile="tsp100"
            ),
        }
    )
    assert resolve_role_for_settlement(cfg) == PrinterRole.COUNTER


def test_settlement_falls_back_when_counter_unassigned() -> None:
    cfg = AppConfig(
        printers={
            "kitchen": PrinterConfig(
                role="kitchen", queue="spock-kitchen", profile="tsp100"
            ),
            "counter": PrinterConfig(
                role="counter", queue="", profile="tsp100", enabled=True
            ),
            "small": PrinterConfig(
                role="small", queue="spock-small", profile="pos5890k"
            ),
        }
    )
    assert resolve_role_for_settlement(cfg) == PrinterRole.KITCHEN


def test_settlement_skips_disabled_counter() -> None:
    cfg = AppConfig(
        printers={
            "counter": PrinterConfig(
                role="counter", queue="Theke", profile="tsp100", enabled=False
            ),
            "small": PrinterConfig(
                role="small", queue="Mini", profile="pos5890k"
            ),
        }
    )
    assert resolve_role_for_settlement(cfg) == PrinterRole.SMALL


def test_items_for_role_filters() -> None:
    order = Order(
        id=5,
        items=[
            OrderItem(qty=1, name="Bier", category="Getränke"),
            OrderItem(qty=1, name="Salat", category="Speisen"),
            OrderItem(qty=1, name="Extra", category="Misc"),
        ],
    )
    routing = RoutingConfig(
        station_role="kitchen",
        category_routing={
            "Getränke": ["counter"],
            "Speisen": ["kitchen"],
        },
    )
    kitchen_items = items_for_role(order, PrinterRole.KITCHEN, routing)
    names = [i.name for i in kitchen_items]
    assert "Salat" in names
    assert "Extra" in names  # unmapped → station
    assert "Bier" not in names

    counter_items = items_for_role(order, PrinterRole.COUNTER, routing)
    assert [i.name for i in counter_items] == ["Bier"]
