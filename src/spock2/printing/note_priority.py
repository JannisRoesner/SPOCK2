"""PICARD-Zettel-Prioritäten für Bon-Layout (Icon + Label + Icon in einer Zeile)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from spock2.printing.profiles.base import PrinterProfile

NotePriority = Literal["normal", "wichtig", "dringend"]

WARNING_ICON = "\u26a0"  # ⚠ — in JetBrains Mono / Consolas
PRIORITY_LABELS: dict[NotePriority, str] = {
    "wichtig": "WICHTIG",
    "dringend": "DRINGEND",
}
PRIORITY_LINE_RE = re.compile(r"^@PRIO:(wichtig|dringend):([A-ZÄÖÜ]+)@$")


@dataclass(frozen=True, slots=True)
class ParsedPriorityLine:
    icon: str  # ``warning`` | ``siren``
    label: str


def normalize_note_priority(value: object | None) -> NotePriority:
    """Normalisiert PICARD-Prioritätswerte (tolerant, inkl. Legacy)."""
    if value is None:
        return "normal"
    text = str(value).strip().casefold()
    if text in {"", "normal", "niedrig", "low"}:
        return "normal"
    if text in {"wichtig", "hoch", "high", "important", "warnung"}:
        return "wichtig"
    if text in {"dringend", "urgent", "kritisch", "critical"}:
        return "dringend"
    return "normal"


def priority_line_marker(level: NotePriority, label: str) -> str:
    return f"@PRIO:{level}:{label}@"


def parse_priority_line(line: str) -> ParsedPriorityLine | None:
    """Erkennt eine kombinierte Prioritätszeile (Icon–Label–Icon)."""
    stripped = line.strip()
    match = PRIORITY_LINE_RE.match(stripped)
    if match is None:
        return None
    level = match.group(1)
    label = match.group(2)
    icon = "siren" if level == "dringend" else "warning"
    return ParsedPriorityLine(icon=icon, label=label)


def note_priority_display_lines(
    priority: object | None,
    profile: PrinterProfile,
) -> list[str]:
    """Eine zentrierte Prioritätszeile oder leer bei normal."""
    level = normalize_note_priority(priority)
    if level not in PRIORITY_LABELS:
        return []
    label = PRIORITY_LABELS[level]
    return [profile.center(priority_line_marker(level, label))]


def note_priority_display_line(
    priority: object | None,
    profile: PrinterProfile,
) -> str | None:
    lines = note_priority_display_lines(priority, profile)
    return lines[0] if lines else None
