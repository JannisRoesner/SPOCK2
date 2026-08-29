"""Tests für den CUPS-Transport: Job-Optionen und Fallback."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from spock2.api.errors import PrintFailed
from spock2.domain.orders import Order, OrderItem
from spock2.domain.print_job import PrinterRole
from spock2.printing import cups_transport
from spock2.printing.cups_transport import CupsTransport
from spock2.printing.gdi_layout import gdi_layout_profile
from spock2.printing.profiles.tsp100 import TSP100
from spock2.printing.receipt_pdf import render_receipt_pdf
from spock2.printing.renderer import ReceiptRenderer


@pytest.fixture
def cups_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """``import cups`` ist unter Windows/CI nicht verfügbar."""
    monkeypatch.setattr(cups_transport, "_cups", MagicMock())


def _bon_pdf() -> bytes:
    order = Order(
        id=7,
        table_number=2,
        waiter="Test",
        items=[OrderItem(qty=2, name="Brezelchen", category="Speisen")],
    )
    profile = gdi_layout_profile(TSP100)
    text = ReceiptRenderer().format_order(order, profile, role=PrinterRole.KITCHEN)
    return render_receipt_pdf(
        text,
        page_width_pt=profile.printable_width_pt,
        line_width=profile.line_width_chars,
    )


def _submitted_options(conn: Any) -> dict[str, str]:
    return conn.printFile.call_args.args[3]


def test_submit_pdf_pins_roll_geometry(cups_stub: None) -> None:
    conn = MagicMock()
    conn.printFile.return_value = 42
    transport = CupsTransport(connection=conn)

    assert transport.submit("spock-kitchen", _bon_pdf(), "Bon") == 42
    options = _submitted_options(conn)
    assert options["document-format"] == "application/pdf"
    assert options["orientation-requested"] == "3"
    assert options["media"].startswith("Custom.204x")


def test_submit_text_without_geometry_options(cups_stub: None) -> None:
    conn = MagicMock()
    conn.printFile.return_value = 1
    transport = CupsTransport(connection=conn)

    transport.submit("spock-small", b"KUECHEN-BON\n", "Bon")
    assert _submitted_options(conn) == {"document-format": "text/plain"}


def test_submit_retries_without_options_when_ppd_rejects(cups_stub: None) -> None:
    """Queue ohne Custom-PageSize: gedrehter Bon ist besser als kein Bon."""
    conn = MagicMock()
    conn.printFile.side_effect = [RuntimeError("unsupported media"), 99]
    transport = CupsTransport(connection=conn)

    assert transport.submit("spock-kitchen", _bon_pdf(), "Bon") == 99
    assert conn.printFile.call_count == 2
    assert _submitted_options(conn) == {"document-format": "application/pdf"}


def test_submit_raises_when_retry_also_fails(cups_stub: None) -> None:
    conn = MagicMock()
    conn.printFile.side_effect = RuntimeError("queue down")
    transport = CupsTransport(connection=conn)

    with pytest.raises(PrintFailed):
        transport.submit("spock-kitchen", _bon_pdf(), "Bon")
