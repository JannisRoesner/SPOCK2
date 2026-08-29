"""Unit-Tests: Hinweisstreifen des Hauptfensters (TLS, Drucker)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from spock2.config.models import AppConfig
from spock2.domain.status import ApiStatus, PrinterStatus
from spock2.ui.main_window import MainWindow


class FakeOrderService(QObject):
    """Minimaler Ersatz für OrderService (nur was MainWindow anfasst)."""

    orders_changed = Signal(object)
    connection_changed = Signal(object)
    complete_finished = Signal(int, bool, str)

    def __init__(self) -> None:
        super().__init__()
        self.orders: list[object] = []
        self.cache_updated_at = datetime.now(UTC)

    def is_completing(self, _order_id: int) -> bool:
        return False


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    return app


@pytest.fixture
def window(qapp: QApplication) -> Iterator[MainWindow]:
    cfg = AppConfig()
    cfg.ui.fullscreen = False
    win = MainWindow(cfg, FakeOrderService())
    yield win
    win.close()


def _tls_status() -> ApiStatus:
    status = ApiStatus()
    status.mark_error("RIKER TLS error: certificate verify failed", kind="TlsError")
    return status


def test_tls_error_shows_banner_once(window: MainWindow) -> None:
    window._on_riker_connection(_tls_status())
    assert window._banner.isVisibleTo(window)
    text = window._banner_text.text()
    assert "Zertifikat" in text
    assert "TLS" in text

    # Der Poller wiederholt den Fehler – der Streifen darf nicht erneut aufpoppen.
    window._hide_banner()
    window._on_riker_connection(_tls_status())
    assert not window._banner.isVisibleTo(window)


def test_tls_banner_returns_after_recovery(window: MainWindow) -> None:
    window._on_riker_connection(_tls_status())
    window._hide_banner()

    ok = ApiStatus()
    ok.mark_success()
    window._on_riker_connection(ok)
    window._on_riker_connection(_tls_status())
    assert window._banner.isVisibleTo(window)


def test_printer_problem_shows_queue_name(window: MainWindow) -> None:
    bad = PrinterStatus(role="kitchen", queue_name="spock-kitchen")
    bad.mark_checked(
        online=False, accepting_jobs=False, error="Queue fehlt: spock-kitchen"
    )
    window.set_printer_statuses([bad])
    assert "Queue fehlt: spock-kitchen" in window._banner_text.text()

    window._hide_banner()
    window.set_printer_statuses([bad])
    assert not window._banner.isVisibleTo(window)


def test_healthy_printers_stay_quiet(window: MainWindow) -> None:
    ok = PrinterStatus(role="kitchen", queue_name="Star")
    ok.mark_checked(online=True, accepting_jobs=True)
    window.set_printer_statuses([ok])
    assert not window._banner.isVisibleTo(window)
