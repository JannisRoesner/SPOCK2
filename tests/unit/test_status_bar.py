"""Unit-Tests: Statusleisten-Texte (lesbar statt abgeschnitten)."""

from __future__ import annotations

from spock2.domain.status import ApiStatus, PrinterStatus
from spock2.ui.widgets.status_bar import _api_label, _printer_label, short_error

_TLS_RAW = (
    "RIKER TLS error: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
    "self-signed certificate (_ssl.c:1081)"
)


def test_tls_error_gets_readable_label() -> None:
    status = ApiStatus()
    status.mark_error(_TLS_RAW, kind="TlsError")
    assert short_error(status) == "Zertifikatsfehler"
    text, object_name = _api_label("RIKER", status)
    assert text == "RIKER: Zertifikatsfehler"
    assert object_name == "statusErr"


def test_unknown_error_kind_is_shortened() -> None:
    status = ApiStatus()
    status.mark_error("x" * 90, kind="SomethingElse")
    assert len(short_error(status)) <= 28


def test_connected_label() -> None:
    status = ApiStatus()
    status.mark_success()
    assert _api_label("PICARD", status) == ("PICARD: online", "statusOk")


def test_printer_label_names_the_reason() -> None:
    bad = PrinterStatus(role="kitchen", queue_name="spock-kitchen")
    bad.mark_checked(
        online=False, accepting_jobs=False, error="Queue fehlt: spock-kitchen"
    )
    text, object_name = _printer_label([bad])
    assert text == "Drucker kitchen: Queue fehlt: spock-kitchen"
    assert object_name == "statusErr"


def test_printer_label_ok_and_empty() -> None:
    ok = PrinterStatus(role="counter", queue_name="Star")
    ok.mark_checked(online=True, accepting_jobs=True)
    assert _printer_label([ok]) == ("Drucker: bereit", "statusOk")
    assert _printer_label([]) == ("Drucker: —", "statusLabel")
