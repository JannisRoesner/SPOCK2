"""Unit-Tests: Wartezeit-Anzeige der Bestellkarte."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from spock2.ui.widgets.order_card import format_wait_time

NOW = datetime(2026, 8, 29, 20, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("delta", "expected", "hot"),
    [
        (timedelta(seconds=20), "< 1 Min", False),
        (timedelta(minutes=3), "3 Min", False),
        (timedelta(minutes=12), "12 Min", True),
        (timedelta(minutes=59), "59 Min", True),
        (timedelta(hours=2, minutes=5), "2:05 h", True),
        (timedelta(days=37, hours=5, minutes=36), "37 T 5 h", True),
    ],
)
def test_format_wait_time(delta: timedelta, expected: str, hot: bool) -> None:
    text, is_hot = format_wait_time((NOW - delta).isoformat(), now=NOW)
    assert text == expected
    assert is_hot is hot


def test_format_wait_time_handles_missing_and_broken_values() -> None:
    assert format_wait_time(None, now=NOW) == ("—", False)
    assert format_wait_time("keine Zeit", now=NOW) == ("—", False)


def test_naive_timestamps_are_treated_as_utc() -> None:
    naive = (NOW - timedelta(minutes=5)).replace(tzinfo=None).isoformat()
    assert format_wait_time(naive, now=NOW) == ("5 Min", False)


def test_future_timestamps_do_not_go_negative() -> None:
    text, hot = format_wait_time((NOW + timedelta(minutes=10)).isoformat(), now=NOW)
    assert text == "< 1 Min"
    assert hot is False
