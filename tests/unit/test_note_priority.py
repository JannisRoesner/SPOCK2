"""Tests für PICARD-Zettel-Prioritäts-Icons."""

from __future__ import annotations

from spock2.printing.note_priority import (
    normalize_note_priority,
    note_priority_display_lines,
    parse_priority_line,
    priority_line_marker,
)
from spock2.printing.profiles.tsp100 import TSP100


def test_normalize_note_priority_values() -> None:
    assert normalize_note_priority(None) == "normal"
    assert normalize_note_priority("normal") == "normal"
    assert normalize_note_priority("wichtig") == "wichtig"
    assert normalize_note_priority("hoch") == "wichtig"
    assert normalize_note_priority("dringend") == "dringend"
    assert normalize_note_priority("urgent") == "dringend"


def test_note_priority_display_lines_single_row() -> None:
    profile = TSP100
    assert note_priority_display_lines("normal", profile) == []
    wichtig = note_priority_display_lines("wichtig", profile)
    assert len(wichtig) == 1
    assert wichtig[0] == profile.center(priority_line_marker("wichtig", "WICHTIG"))
    dringend = note_priority_display_lines("dringend", profile)
    assert len(dringend) == 1
    assert dringend[0] == profile.center(priority_line_marker("dringend", "DRINGEND"))


def test_parse_priority_line() -> None:
    parsed = parse_priority_line("@PRIO:wichtig:WICHTIG@")
    assert parsed is not None
    assert parsed.icon == "warning"
    assert parsed.label == "WICHTIG"
    parsed = parse_priority_line("@PRIO:dringend:DRINGEND@")
    assert parsed is not None
    assert parsed.icon == "siren"
    assert parsed.label == "DRINGEND"
    assert parse_priority_line("ZETTEL") is None
