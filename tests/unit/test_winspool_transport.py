"""Unit-Tests: Transportwahl, queue-Alias, gemockter WinSpool."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from spock2.api.errors import CupsUnavailable, PrintFailed
from spock2.app import create_transport
from spock2.config.models import AppConfig, PrintConfig, PrinterConfig, default_state_dir
from spock2.printing.file_transport import FileTransport
from spock2.printing.winspool_transport import (
    WinSpoolTransport,
    _map_job_status,
    winspool_available,
)
from spock2.workers.print_worker import PrintWorker


def test_printer_config_queue_alias_cups_queue() -> None:
    printer = PrinterConfig.model_validate(
        {"role": "kitchen", "cups_queue": "spock-kitchen", "profile": "tsp100"}
    )
    assert printer.queue == "spock-kitchen"


def test_printer_config_queue_field() -> None:
    printer = PrinterConfig(role="kitchen", queue="Star TSP100 Kitchen", profile="tsp100")
    assert printer.queue == "Star TSP100 Kitchen"
    dumped = printer.model_dump()
    assert dumped["queue"] == "Star TSP100 Kitchen"
    assert "cups_queue" not in dumped


def test_print_transport_mode_includes_winspool() -> None:
    cfg = PrintConfig(transport="winspool")
    assert cfg.transport == "winspool"


def test_create_transport_file_mode() -> None:
    cfg = AppConfig(print=PrintConfig(transport="file"))
    assert isinstance(create_transport(cfg), FileTransport)


def test_create_transport_auto_windows_without_winspool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    with (
        patch("spock2.app.cups_available", return_value=False),
        patch("spock2.app.winspool_available", return_value=False),
    ):
        transport = create_transport(AppConfig(print=PrintConfig(transport="auto")))
    assert isinstance(transport, FileTransport)


def test_create_transport_auto_windows_with_winspool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    fake = MagicMock(spec=WinSpoolTransport)
    with (
        patch("spock2.app.cups_available", return_value=False),
        patch("spock2.app.winspool_available", return_value=True),
        patch("spock2.app.WinSpoolTransport", return_value=fake) as ctor,
    ):
        transport = create_transport(AppConfig(print=PrintConfig(transport="auto")))
    ctor.assert_called_once()
    assert transport is fake


def test_create_transport_winspool_hard_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    with (
        patch("spock2.app.winspool_available", return_value=True),
        patch(
            "spock2.app.WinSpoolTransport",
            side_effect=CupsUnavailable("kein Spooler"),
        ),
        pytest.raises(CupsUnavailable),
    ):
        create_transport(AppConfig(print=PrintConfig(transport="winspool")))


def test_default_state_dir_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert default_state_dir() == tmp_path / "spock2"


def test_map_job_status_bits() -> None:
    assert _map_job_status(0x00000010) == "printing"  # PRINTING
    assert _map_job_status(0x00000080) == "completed"  # PRINTED
    assert _map_job_status(0x00000002) == "failed"  # ERROR
    assert _map_job_status(0x00000100) == "cancelled"  # DELETED


def test_winspool_transport_mocked_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    fake_wp = MagicMock()
    fake_wp.OpenPrinter.return_value = "HANDLE"
    fake_wp.StartDocPrinter.return_value = 42
    fake_wp.WritePrinter.return_value = 5
    fake_wp.EnumPrinters.return_value = [(0, "", "Star Kitchen", "")]
    fake_wp.PRINTER_ENUM_LOCAL = 2
    fake_wp.PRINTER_ENUM_CONNECTIONS = 4

    monkeypatch.setattr(
        "spock2.printing.winspool_transport._win32print",
        fake_wp,
    )
    monkeypatch.setattr(
        "spock2.printing.winspool_transport._WIN32_IMPORT_ERROR",
        None,
    )

    transport = WinSpoolTransport()
    job_id = transport.submit("Star Kitchen", b"\x1b@hello", "test")
    assert job_id == 42
    fake_wp.StartDocPrinter.assert_called()
    fake_wp.WritePrinter.assert_called_with("HANDLE", b"\x1b@hello")
    assert "Star Kitchen" in transport.list_queues()
    assert transport.is_available()


def test_winspool_unavailable_on_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert winspool_available() is False
    with pytest.raises(CupsUnavailable):
        WinSpoolTransport()


def test_prefer_escpos_winspool_small_printer() -> None:
    worker = PrintWorker(
        db_path=":memory:",
        config=AppConfig(),
        transport=MagicMock(spec=WinSpoolTransport),
    )
    worker.transport = object.__new__(WinSpoolTransport)
    profile = SimpleNamespace(capabilities=("escpos",), name="pos5890k")
    assert worker._prefer_gdi(profile) is False
    assert worker._prefer_escpos(profile) is True


def test_prefer_gdi_tsp100_winspool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("spock2.workers.print_worker.gdi_available", lambda: True)
    worker = PrintWorker(
        db_path=":memory:",
        config=AppConfig(),
        transport=MagicMock(spec=WinSpoolTransport),
    )
    worker.transport = object.__new__(WinSpoolTransport)
    profile = SimpleNamespace(capabilities=("cutter", "gdi"), name="tsp100")
    assert worker._prefer_gdi(profile) is True
    assert worker._prefer_escpos(profile) is False


def test_prefer_escpos_tsp100_without_gdi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("spock2.workers.print_worker.gdi_available", lambda: False)
    worker = PrintWorker(
        db_path=":memory:",
        config=AppConfig(),
        transport=MagicMock(spec=WinSpoolTransport),
    )
    worker.transport = object.__new__(WinSpoolTransport)
    profile = SimpleNamespace(capabilities=("cutter", "gdi"), name="tsp100")
    assert worker._prefer_gdi(profile) is False
    assert worker._prefer_escpos(profile) is True


def test_prefer_escpos_file_with_capability() -> None:
    worker = PrintWorker(
        db_path=":memory:",
        config=AppConfig(),
        transport=FileTransport(),
    )
    profile = SimpleNamespace(capabilities=("escpos",), name="pos5890k")
    assert worker._prefer_escpos(profile) is True
    profile_no = SimpleNamespace(capabilities=("cutter",), name="tsp100")
    assert worker._prefer_escpos(profile_no) is False


def test_prefer_cups_pdf() -> None:
    from spock2.printing.cups_transport import CupsTransport

    cups = object.__new__(CupsTransport)
    worker = PrintWorker(
        db_path=":memory:",
        config=AppConfig(),
        transport=cups,
    )
    tsp = SimpleNamespace(capabilities=("gdi",), name="tsp100")
    small = SimpleNamespace(capabilities=("escpos",), name="pos5890k")
    assert worker._prefer_cups_pdf(tsp) is True
    assert worker._prefer_cups_pdf(small) is False
    worker.transport = FileTransport()
    assert worker._prefer_cups_pdf(tsp) is False


def test_prefer_escpos_cups_never() -> None:
    from spock2.printing.cups_transport import CupsTransport

    cups = object.__new__(CupsTransport)
    worker = PrintWorker(
        db_path=":memory:",
        config=AppConfig(),
        transport=cups,
    )
    profile = SimpleNamespace(capabilities=("escpos",), name="pos5890k")
    assert worker._prefer_escpos(profile) is False


def test_winspool_submit_empty_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    fake_wp = MagicMock()
    monkeypatch.setattr("spock2.printing.winspool_transport._win32print", fake_wp)
    monkeypatch.setattr("spock2.printing.winspool_transport._WIN32_IMPORT_ERROR", None)
    transport = WinSpoolTransport()
    with pytest.raises(PrintFailed):
        transport.submit("", b"x", "t")


def test_winspool_submit_gdi_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    fake_wp = MagicMock()
    monkeypatch.setattr("spock2.printing.winspool_transport._win32print", fake_wp)
    monkeypatch.setattr("spock2.printing.winspool_transport._WIN32_IMPORT_ERROR", None)

    called: dict[str, object] = {}

    def fake_gdi(printer: str, text: str, job_name: str, **kwargs: object) -> None:
        called["printer"] = printer
        called["text"] = text
        called["job_name"] = job_name

    monkeypatch.setattr("spock2.printing.gdi_print.gdi_print_text", fake_gdi)
    fake_wp.OpenPrinter.return_value = "HANDLE"
    fake_wp.EnumJobs.return_value = []
    transport = WinSpoolTransport()
    job_id = transport.submit_gdi("Star Kitchen", "KÜCHEN-BON\nTisch: 4", "Order-9")
    assert job_id == 1_000_000
    assert called["printer"] == "Star Kitchen"
    assert "KÜCHEN-BON" in str(called["text"])
    assert transport.get_job_state(job_id) == "completed"
