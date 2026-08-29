"""Unit-Tests: Spaltenzahl der Kartenfläche."""

from __future__ import annotations

import pytest

from spock2.ui.main_window import wanted_columns


@pytest.mark.parametrize(
    ("width", "expected"),
    [
        (0, 1),
        (600, 1),
        (800, 2),
        (1024, 2),
        (1280, 3),
        (1600, 4),
        (1920, 4),
        (3840, 4),
    ],
)
def test_wanted_columns(width: int, expected: int) -> None:
    assert wanted_columns(width) == expected
