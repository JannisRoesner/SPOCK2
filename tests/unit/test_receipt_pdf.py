"""Tests für CUPS-PDF-Bons (Alt-SPOCK-Look)."""

from __future__ import annotations

from spock2.domain.notes import Note
from spock2.domain.orders import Order, OrderItem
from spock2.domain.print_job import PrinterRole
from spock2.printing.cups_transport import cups_payload_format
from spock2.printing.gdi_layout import (
    GDI_LINE_WIDTH,
    GdiLineKind,
    classify_line,
    gdi_layout_profile,
)
from spock2.printing.profiles.tsp100 import TSP100
from spock2.printing.receipt_pdf import RuleOp, TextOp, layout_receipt, render_receipt_pdf
from spock2.printing.renderer import ReceiptRenderer


def test_cups_payload_format_pdf_vs_text() -> None:
    assert cups_payload_format(b"%PDF-1.4\n") == ("application/pdf", ".pdf")
    assert cups_payload_format(b"KUECHEN-BON") == ("text/plain", ".txt")


def test_classify_note_priority_header() -> None:
    lines = ["=" * 32, "ZETTEL".center(32), "(HOCH)".center(32), "=" * 32]
    assert classify_line(lines[1], 1).kind == GdiLineKind.HEADER
    assert classify_line(lines[2], 2).kind == GdiLineKind.HEADER


def test_pdf_order_has_large_table_and_rules() -> None:
    order = Order(
        id=9,
        table_number=4,
        waiter="Jannis",
        items=[
            OrderItem(qty=3, name="Brezelchen", category="Speisen"),
            OrderItem(qty=1, name="Brötchen", notes="Mett", category="Speisen"),
        ],
    )
    text = ReceiptRenderer().format_order(
        order, gdi_layout_profile(TSP100), role=PrinterRole.KITCHEN
    )
    layout = layout_receipt(text, paper_width_mm=80, line_width=GDI_LINE_WIDTH)
    headers = [op for op in layout.ops if isinstance(op, TextOp) and op.text == "KÜCHEN-BON"]
    assert headers
    assert headers[0].size == layout.header_pt
    assert headers[0].bold is True

    tables = [op for op in layout.ops if isinstance(op, TextOp) and op.text == "4"]
    assert tables
    assert tables[0].size == layout.table_pt
    assert tables[0].size > layout.header_pt

    assert any(isinstance(op, RuleOp) and op.double for op in layout.ops)
    qty = [op for op in layout.ops if isinstance(op, TextOp) and op.text == "3x "]
    assert qty and qty[0].bold is True


def test_pdf_note_large_zettel_title() -> None:
    note = Note(
        id="n1",
        text="Bitte Tisch 4 bedienen – dringend!",
        sender="Moderation",
        priority="hoch",
        timestamp="2026-07-23T15:00:00+02:00",
    )
    text = ReceiptRenderer().format_note(note, gdi_layout_profile(TSP100))
    layout = layout_receipt(text, paper_width_mm=80)
    titles = [op for op in layout.ops if isinstance(op, TextOp) and op.text == "ZETTEL"]
    assert titles and titles[0].size == layout.header_pt
    prio = [op for op in layout.ops if isinstance(op, TextOp) and "(HOCH)" in op.text]
    assert prio and prio[0].bold is True


def test_render_receipt_pdf_bytes_and_umlauts() -> None:
    order = Order(
        id=3,
        table_number=1,
        items=[OrderItem(qty=1, name="Käsespätzle", category="Speisen")],
    )
    text = ReceiptRenderer().format_order(
        order, gdi_layout_profile(TSP100), role=PrinterRole.KITCHEN
    )
    pdf = render_receipt_pdf(text, paper_width_mm=80)
    assert pdf.startswith(b"%PDF")
    assert b"/Courier" in pdf
    assert "Käsespätzle".encode("cp1252") in pdf
    assert b"%%EOF" in pdf
