"""Tests für CUPS-PDF-Bons (Alt-SPOCK-Look)."""

from __future__ import annotations

import pytest

from spock2.domain.notes import Note
from spock2.domain.orders import Order, OrderItem
from spock2.domain.print_job import PrinterRole
from spock2.printing.cups_transport import (
    cups_job_options,
    cups_media_option,
    cups_payload_format,
)
from spock2.printing.gdi_layout import (
    GDI_LINE_WIDTH,
    GdiLineKind,
    classify_line,
    gdi_layout_profile,
)
from spock2.printing.profiles.tsp100 import TSP100
from spock2.printing.receipt_fonts import build_receipt_fonts
from spock2.printing.receipt_pdf import (
    IconOp,
    ReceiptLayout,
    RuleOp,
    TextOp,
    layout_receipt,
    pdf_media_size_pt,
    render_receipt_pdf,
)
from spock2.printing.renderer import ReceiptRenderer

# Bedruckbare Breite der 80-mm-Rolle: 576 Punkte @ 203 dpi = 204 pt = 72 mm.
PAGE_W_PT = TSP100.printable_width_pt


def test_cups_payload_format_pdf_vs_text() -> None:
    assert cups_payload_format(b"%PDF-1.4\n") == ("application/pdf", ".pdf")
    assert cups_payload_format(b"KUECHEN-BON") == ("text/plain", ".txt")


def test_classify_note_priority_header() -> None:
    line = "ZETTEL".center(32)
    prio = "@PRIO:wichtig:WICHTIG@".center(32)
    lines = ["=" * 32, line, prio, "=" * 32]
    assert classify_line(lines[1], 1).kind == GdiLineKind.HEADER
    parsed = classify_line(lines[2], 2)
    assert parsed.kind == GdiLineKind.PRIORITY_LINE
    assert parsed.priority_icon == "warning"
    assert parsed.priority_label == "WICHTIG"


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
    layout = layout_receipt(text, page_width_pt=PAGE_W_PT, line_width=GDI_LINE_WIDTH)
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
        priority="wichtig",
        timestamp="2026-07-23T15:00:00+02:00",
    )
    text = ReceiptRenderer().format_note(note, gdi_layout_profile(TSP100))
    layout = layout_receipt(text, page_width_pt=PAGE_W_PT)
    titles = [op for op in layout.ops if isinstance(op, TextOp) and op.text == "ZETTEL"]
    assert titles and titles[0].size == layout.header_pt
    prio = [op for op in layout.ops if isinstance(op, TextOp) and op.text == "\u26a0"]
    assert len(prio) == 2
    labels = [op for op in layout.ops if isinstance(op, TextOp) and op.text == "WICHTIG"]
    assert len(labels) == 1


def test_pdf_note_dringend_renders_siren_icon() -> None:
    note = Note(
        id="n2",
        text="Sofort an die Theke!",
        sender="Moderation",
        priority="dringend",
        timestamp="2026-07-23T15:05:00+02:00",
    )
    text = ReceiptRenderer().format_note(note, gdi_layout_profile(TSP100))
    layout = layout_receipt(text, page_width_pt=PAGE_W_PT)
    sirens = [op for op in layout.ops if isinstance(op, IconOp) and op.kind == "siren"]
    assert len(sirens) == 2
    labels = [op for op in layout.ops if isinstance(op, TextOp) and op.text == "DRINGEND"]
    assert len(labels) == 1
    pdf = render_receipt_pdf(text, page_width_pt=PAGE_W_PT)
    assert pdf.startswith(b"%PDF")
    assert b" arc " in pdf


def test_pdf_note_normal_has_no_priority_icon() -> None:
    note = Note(
        id="n3",
        text="Alles ok.",
        sender="Küche",
        priority="normal",
    )
    text = ReceiptRenderer().format_note(note, gdi_layout_profile(TSP100))
    layout = layout_receipt(text, page_width_pt=PAGE_W_PT)
    assert not any(isinstance(op, IconOp) for op in layout.ops)
    assert not any(
        isinstance(op, TextOp) and op.text in {"\u26a0", "WICHTIG", "DRINGEND"}
        for op in layout.ops
    )


def test_render_receipt_pdf_bytes_and_umlauts() -> None:
    order = Order(
        id=3,
        table_number=1,
        items=[OrderItem(qty=1, name="Käsespätzle", category="Speisen")],
    )
    text = ReceiptRenderer().format_order(
        order, gdi_layout_profile(TSP100), role=PrinterRole.KITCHEN
    )
    pdf = render_receipt_pdf(text, page_width_pt=PAGE_W_PT)
    assert pdf.startswith(b"%PDF")
    assert b"/Subtype /Type0" in pdf
    assert b"JBMono" in pdf
    assert b"<00E4>" in pdf  # ä in ToUnicode, nicht als CID
    fonts = build_receipt_fonts(text)
    auml_gid = fonts.regular.unicode_to_gid[ord("ä")]
    assert fonts.regular.pdf_hex_text("ä") == f"<{auml_gid:04X}>".encode("ascii")
    assert auml_gid != ord("ä")
    assert b"%%EOF" in pdf
    assert b"/Rotate 0" in pdf


def _order_with_items(count: int, *, category: str = "Speisen") -> Order:
    return Order(
        id=15,
        table_number=1,
        waiter="Test",
        items=[
            OrderItem(qty=1, name=f"Position {i}", notes="Ketchup", category=category)
            for i in range(count)
        ],
    )


def _layout_for(count: int) -> ReceiptLayout:
    text = ReceiptRenderer().format_order(
        _order_with_items(count), gdi_layout_profile(TSP100), role=PrinterRole.KITCHEN
    )
    return layout_receipt(text, page_width_pt=PAGE_W_PT, line_width=GDI_LINE_WIDTH)


def test_page_width_is_printable_width_not_roll_width() -> None:
    """Die Star-PPD erlaubt max. 204 pt Breite – 80 mm (227 pt) lehnt sie ab."""
    assert PAGE_W_PT == 204
    assert _layout_for(3).page_w == 204.0


@pytest.mark.parametrize("count", [0, 1, 2, 5, 20, 60])
def test_pdf_page_is_always_portrait(count: int) -> None:
    """Querformatige Seiten werden von pdftopdf um 90° gedreht."""
    layout = _layout_for(count)
    assert layout.page_h > layout.page_w


@pytest.mark.parametrize("count", [0, 1, 2, 5, 20, 60])
def test_pdf_page_dimensions_are_whole_points(count: int) -> None:
    """Nur ganze Punkte lassen sich verlustfrei als ``Custom.BxH`` anfordern."""
    layout = _layout_for(count)
    assert layout.page_w == int(layout.page_w)
    assert layout.page_h == int(layout.page_h)


def test_pdf_page_grows_with_content() -> None:
    short = _layout_for(2)
    long = _layout_for(40)
    assert long.page_h > short.page_h


def test_pdf_font_size_independent_of_content_length() -> None:
    """Gleiche Schriftgröße auf Küchen- und Theken-Bon, egal wie lang."""
    assert _layout_for(2).base_pt == _layout_for(40).base_pt == 10.0


def test_pdf_content_stays_inside_page() -> None:
    layout = _layout_for(8)
    for op in layout.ops:
        if isinstance(op, TextOp):
            right = op.x + len(op.text) * op.size * 0.6
            assert op.x >= 0
            assert right <= layout.page_w


def test_pdf_media_option_matches_page_exactly() -> None:
    text = ReceiptRenderer().format_order(
        _order_with_items(6), gdi_layout_profile(TSP100), role=PrinterRole.KITCHEN
    )
    layout = layout_receipt(text, page_width_pt=PAGE_W_PT, line_width=GDI_LINE_WIDTH)
    pdf = render_receipt_pdf(text, page_width_pt=PAGE_W_PT, line_width=GDI_LINE_WIDTH)

    assert pdf_media_size_pt(pdf) == (layout.page_w, layout.page_h)
    assert cups_media_option(pdf) == f"Custom.204x{int(layout.page_h)}"


def test_cups_job_options_pin_geometry_for_pdf() -> None:
    pdf = render_receipt_pdf(
        ReceiptRenderer().format_order(
            _order_with_items(3), gdi_layout_profile(TSP100), role=PrinterRole.KITCHEN
        ),
        page_width_pt=PAGE_W_PT,
    )
    options = cups_job_options(pdf)
    assert options["document-format"] == "application/pdf"
    assert options["nopdfAutoRotate"] == "true"
    assert options["orientation-requested"] == "3"
    assert options["print-scaling"] == "none"
    assert options["fit-to-page"] == "false"
    assert options["media"].startswith("Custom.204x")


def test_cups_job_options_plain_text_only_format() -> None:
    assert cups_job_options(b"KUECHEN-BON\n") == {"document-format": "text/plain"}
    assert cups_media_option(b"KUECHEN-BON\n") is None
