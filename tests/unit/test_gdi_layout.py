"""Tests für GDI-Layout (Alt-SPOCK TSP100)."""

from __future__ import annotations

from spock2.domain.orders import Order, OrderItem
from spock2.domain.print_job import PrinterRole
from spock2.printing.gdi_layout import (
    GDI_LINE_WIDTH,
    GdiLineKind,
    classify_line,
    gdi_layout_profile,
    profile_uses_gdi,
    split_table_meta,
    use_large_table_font,
)
from spock2.printing.profiles.pos5890k import POS5890K
from spock2.printing.profiles.tsp100 import TSP100
from spock2.printing.renderer import ReceiptRenderer


def test_tsp100_uses_gdi_capability() -> None:
    assert profile_uses_gdi(TSP100) is True
    assert profile_uses_gdi(POS5890K) is False


def test_gdi_layout_profile_is_32_chars() -> None:
    gdi = gdi_layout_profile(TSP100)
    assert gdi.line_width_chars == GDI_LINE_WIDTH
    assert TSP100.line_width_chars == 42


def test_classify_header_and_table_meta() -> None:
    lines = [
        "=" * 32,
        "KÜCHEN-BON".center(32),
        "=" * 32,
        "Bestell-Nr.: 9   Tisch: 4",
        "-" * 32,
        "[SPEISEN]",
        "3x Brezelchen",
        "1x Brötchen",
        "  -> Mett",
    ]
    kinds = [classify_line(line, i).kind for i, line in enumerate(lines)]
    assert kinds[1] == GdiLineKind.HEADER
    assert kinds[3] == GdiLineKind.TABLE_META
    assert kinds[5] == GdiLineKind.CATEGORY
    assert kinds[6] == GdiLineKind.QTY
    assert kinds[8] == GdiLineKind.BODY


def test_split_table_meta() -> None:
    order_part, table = split_table_meta("Bestell-Nr.: 9   Tisch: 4")
    assert "Bestell-Nr.: 9" in order_part
    assert table == "4"


def test_large_table_font_only_for_short_numbers() -> None:
    assert use_large_table_font("4") is True
    assert use_large_table_font("12") is True
    assert use_large_table_font("Familie Schmidt") is False


def test_gdi_order_format_fits_32_and_keeps_waiter() -> None:
    order = Order(
        id=9,
        table_number=4,
        waiter="Jannis",
        items=[
            OrderItem(qty=3, name="Brezelchen", category="Speisen"),
            OrderItem(qty=1, name="Brötchen", category="Speisen", notes="Mett"),
        ],
    )
    profile = gdi_layout_profile(TSP100)
    text = ReceiptRenderer().format_order(order, profile, role=PrinterRole.KITCHEN)
    assert "KÜCHEN-BON" in text
    assert "Bestell-Nr.: 9" in text
    assert "Tisch: 4" in text
    assert "Bedienung: Jannis" in text
    assert "3x Brezelchen" in text
    assert "  -> Mett" in text
    for line in text.splitlines():
        assert len(line) <= GDI_LINE_WIDTH
    seps = [line for line in text.splitlines() if line and set(line) <= {"="}]
    assert seps
    assert all(len(line) == GDI_LINE_WIDTH for line in seps)
