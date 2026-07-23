"""Hybrid-Routing: Stationsrolle + Kategorie→Rollen."""

from __future__ import annotations

from spock2.config.models import RoutingConfig
from spock2.domain.orders import Order, OrderItem
from spock2.domain.print_job import PrinterRole


def _station_role(routing: RoutingConfig) -> PrinterRole:
    return PrinterRole(routing.station_role)


def _category_map(routing: RoutingConfig) -> dict[str, list[PrinterRole]]:
    """casefold(category) → Rollenliste."""
    out: dict[str, list[PrinterRole]] = {}
    for raw_cat, roles in routing.category_routing.items():
        key = str(raw_cat).strip().casefold()
        if not key:
            continue
        parsed: list[PrinterRole] = []
        for role in roles:
            try:
                parsed.append(PrinterRole(str(role)))
            except ValueError:
                continue
        if parsed:
            out[key] = parsed
    return out


def resolve_roles_for_order(
    order: Order,
    routing: RoutingConfig,
) -> list[PrinterRole]:
    """Ermittelt Zielrollen für eine Bestellung.

    - ``station_role`` ist Default, wenn keine Kategorie-Regel greift.
    - Treffen Regeln zu, werden eindeutige Rollen in Erstauftreten-Reihenfolge
      gesammelt.
    - Bleibt die Liste leer, fällt auf ``station_role`` zurück.
    """
    station = _station_role(routing)
    cat_map = _category_map(routing)
    if not cat_map:
        return [station]

    matched: list[PrinterRole] = []
    seen: set[PrinterRole] = set()
    for item in order.items:
        cat = (item.category or "").strip().casefold()
        if not cat or cat not in cat_map:
            continue
        for role in cat_map[cat]:
            if role not in seen:
                seen.add(role)
                matched.append(role)

    if not matched:
        return [station]
    return matched


def resolve_role_for_note(routing: RoutingConfig) -> PrinterRole:
    """Zettel immer an Stationsrolle (Fallback: kitchen)."""
    try:
        return _station_role(routing)
    except ValueError:
        return PrinterRole.KITCHEN


def items_for_role(
    order: Order,
    role: PrinterRole,
    routing: RoutingConfig,
) -> list[OrderItem]:
    """Filtert Positionen für eine Zielrolle.

    Ohne Kategorie-Treffer (Stations-Fallback): alle Items.
    Mit Regeln: Items, deren Kategorie die Rolle enthält; unmapped Items
    gehen an die Stationsrolle.
    """
    station = _station_role(routing)
    cat_map = _category_map(routing)
    if not cat_map:
        return list(order.items)

    any_match = False
    selected: list[OrderItem] = []
    for item in order.items:
        cat = (item.category or "").strip().casefold()
        if cat and cat in cat_map:
            any_match = True
            if role in cat_map[cat]:
                selected.append(item)
        elif role == station:
            selected.append(item)

    if not any_match:
        return list(order.items)
    return selected
