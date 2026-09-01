"""Unit-Tests für ReceiptRenderer."""

from __future__ import annotations

from spock2.domain.notes import Note
from spock2.domain.orders import Order, OrderItem
from spock2.domain.print_job import PrinterRole
from spock2.printing.profiles import get_profile
from spock2.printing.profiles.pos5890k import POS5890K
from spock2.printing.profiles.tsp100 import TSP100
from spock2.printing.renderer import ReceiptRenderer


def test_umlauts_and_euro_preserved() -> None:
    order = Order(
        id=7,
        table_number=3,
        waiter="Jannis",
        created_at="2026-07-23T14:30:00+02:00",
        items=[
            OrderItem(qty=1, name="Käsespätzle", category="Speisen", notes="mit Soße"),
            OrderItem(qty=2, name="Weißbier", category="Getränke"),
        ],
    )
    renderer = ReceiptRenderer()
    text = renderer.format_order(order, TSP100, role=PrinterRole.KITCHEN)
    assert "KÜCHEN-BON" in text
    assert "Käsespätzle" in text
    assert "Weißbier" in text
    assert "Soße" in text
    assert "ä" in text or "Ä" in text

    raw = renderer.render_to_bytes(text + "\n12,50 €", TSP100)
    decoded = raw.decode("utf-8")
    assert "Käsespätzle" in decoded
    assert "€" in decoded


def test_theken_header_without_redundant_categories() -> None:
    order = Order(
        id=1,
        table_number="5",
        items=[
            OrderItem(qty=1, name="Cola", category="Getränke"),
            OrderItem(qty=1, name="Schnitzel", category="Speisen"),
            OrderItem(qty=1, name="Cola", category="Getränke"),
        ],
    )
    counter = ReceiptRenderer().format_order(order, TSP100, role=PrinterRole.COUNTER)
    assert "THEKEN-BON" in counter
    assert "[GETRÄNKE]" not in counter
    assert "[SPEISEN]" not in counter
    assert "1x Cola" in counter
    assert "1x Schnitzel" in counter

    kitchen = ReceiptRenderer().format_order(order, TSP100, role=PrinterRole.KITCHEN)
    assert "KÜCHEN-BON" in kitchen
    assert "[SPEISEN]" not in kitchen
    assert "[GETRÄNKE]" not in kitchen


def test_small_bon_keeps_category_headers() -> None:
    order = Order(
        id=2,
        table_number="3",
        items=[
            OrderItem(qty=1, name="Cola", category="Getränke"),
            OrderItem(qty=1, name="Brezel", category="Speisen"),
        ],
    )
    text = ReceiptRenderer().format_order(order, TSP100, role=PrinterRole.SMALL)
    assert "KLEIN-BON" in text
    assert "[GETRÄNKE]" in text
    assert "[SPEISEN]" in text


def test_item_notes_arrow() -> None:
    order = Order(
        id=2,
        items=[OrderItem(qty=3, name="Pommes", category="Speisen", notes="ohne Salz")],
    )
    text = ReceiptRenderer().format_order(order, POS5890K, role=PrinterRole.KITCHEN)
    assert "3x Pommes" in text
    assert "  -> ohne Salz" in text


def test_wrap_respects_line_width() -> None:
    long_name = "X" * 80
    order = Order(
        id=3,
        items=[OrderItem(qty=1, name=long_name, category="Speisen")],
    )
    profile = get_profile("pos5890k")
    assert profile.line_width_chars == 32
    text = ReceiptRenderer().format_order(order, profile, role=PrinterRole.KITCHEN)
    for line in text.splitlines():
        assert len(line) <= profile.line_width_chars


def test_note_zettel_layout() -> None:
    note = Note(
        id="n1",
        text="Bitte Tisch 4 bedienen – dringend!",
        sender="Moderation",
        priority="wichtig",
        timestamp="2026-07-23T15:00:00+02:00",
    )
    text = ReceiptRenderer().format_note(note, POS5890K)
    assert "ZETTEL" in text
    assert "@PRIO:wichtig:WICHTIG@" in text
    assert "(WICHTIG)" not in text
    assert "Von: Moderation" in text
    assert "Bitte Tisch 4" in text
    assert "Zeit: 15:00" in text


def test_tsp100_line_width_42() -> None:
    assert TSP100.line_width_chars == 42
    assert TSP100.paper_width_mm == 80
    assert TSP100.supports_cutter is True
    wrapped = TSP100.wrap_text("a " * 30)
    assert all(len(line) <= 42 for line in wrapped)
