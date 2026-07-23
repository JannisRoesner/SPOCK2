"""Unit-Tests: System-Queue-Discovery für Admin-UI."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from spock2.printing.file_transport import FileTransport
from spock2.printing.queue_discovery import list_system_queues


def test_list_system_queues_file_mode() -> None:
    queues = list_system_queues("file")
    assert queues == ["file-kitchen", "file-counter", "file-small"]


def test_list_system_queues_cups_mode() -> None:
    fake = MagicMock()
    fake.list_queues.return_value = ["spock-kitchen", "spock-counter"]
    with patch("spock2.printing.queue_discovery.CupsTransport", return_value=fake):
        assert list_system_queues("cups") == ["spock-kitchen", "spock-counter"]
    fake.list_queues.assert_called_once()


def test_list_system_queues_winspool_mode() -> None:
    fake = MagicMock()
    fake.list_queues.return_value = ["Star Kitchen", "POS-58"]
    with patch("spock2.printing.queue_discovery.WinSpoolTransport", return_value=fake):
        assert list_system_queues("winspool") == ["Star Kitchen", "POS-58"]


def test_list_system_queues_returns_empty_on_error() -> None:
    with patch(
        "spock2.printing.queue_discovery.CupsTransport",
        side_effect=RuntimeError("cups down"),
    ):
        assert list_system_queues("cups") == []


def test_list_system_queues_auto_linux_uses_cups(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    fake = MagicMock()
    fake.list_queues.return_value = ["cups-a"]
    with (
        patch("spock2.printing.queue_discovery.cups_available", return_value=True),
        patch("spock2.printing.queue_discovery.CupsTransport", return_value=fake),
    ):
        assert list_system_queues("auto") == ["cups-a"]


def test_list_system_queues_auto_windows_uses_winspool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    fake = MagicMock()
    fake.list_queues.return_value = ["Win Printer"]
    with (
        patch("spock2.printing.queue_discovery.cups_available", return_value=False),
        patch("spock2.printing.queue_discovery.winspool_available", return_value=True),
        patch("spock2.printing.queue_discovery.WinSpoolTransport", return_value=fake),
    ):
        assert list_system_queues("auto") == ["Win Printer"]


def test_list_system_queues_auto_fallback_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    with (
        patch("spock2.printing.queue_discovery.cups_available", return_value=False),
        patch("spock2.printing.queue_discovery.winspool_available", return_value=False),
    ):
        queues = list_system_queues("auto")
    assert queues == FileTransport().list_queues()
