"""Layout-Regeln für den Alt-SPOCK-TSP100-Look (GDI unter Windows, PDF unter CUPS).

42-Zeichen-Klartext auf 80 mm führt zu Umbruch: Titel wirkt rechtsbündig,
Trennlinien verdoppeln sich, Tischnummer bleibt klein.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum

from spock2.printing.note_priority import parse_priority_line
from spock2.printing.profiles.base import PrinterProfile

# Alt-SPOCK Windows-GDI: 32 Spalten, Consolas 10 pt
GDI_LINE_WIDTH = 32
GDI_FONT_FALLBACKS = ("Consolas", "Courier New", "Lucida Console")
GDI_BASE_PT = 10
GDI_HEADER_SCALE = 1.6
GDI_TABLE_SCALE = 3.2
GDI_LARGE_TABLE_MAX_CHARS = 4

_QTY_RE = re.compile(r"^(\d+)x ")
_HEADER_TITLES = frozenset(
    {
        "KÜCHEN-BON",
        "THEKEN-BON",
        "KLEIN-BON",
        "ZETTEL",
        "SPOCK2 TEST",
    }
)


class GdiLineKind(StrEnum):
    EMPTY = "empty"
    HEADER = "header"
    PRIORITY_LINE = "priority_line"
    TABLE_META = "table_meta"
    CATEGORY = "category"
    QTY = "qty"
    BODY = "body"


@dataclass(frozen=True, slots=True)
class GdiLine:
    """Eine Bon-Zeile plus GDI-Stil."""

    kind: GdiLineKind
    text: str
    qty_token: str = ""
    rest: str = ""
    order_part: str = ""
    table_number: str = ""
    priority_icon: str = ""  # ``warning`` | ``siren``
    priority_label: str = ""


def gdi_layout_profile(profile: PrinterProfile) -> PrinterProfile:
    """80 mm GDI wie Alt-SPOCK: 32 Zeichen, sonst Profilbreite behalten."""
    if profile.paper_width_mm < 80 or profile.line_width_chars == GDI_LINE_WIDTH:
        return profile
    return replace(profile, line_width_chars=GDI_LINE_WIDTH)


def profile_uses_gdi(profile: object) -> bool:
    """TSP100 / Star: GDI über den Windows-Treiber, nicht ESC/POS."""
    caps = tuple(getattr(profile, "capabilities", ()) or ())
    if "gdi" in caps:
        return True
    name = str(getattr(profile, "name", "") or "").strip().casefold()
    return name in {"tsp100", "tsp-100", "star"}


def use_large_table_font(table_number: str) -> bool:
    """Große Tischnummer nur bei kurzen Werten (nicht bei Gastnamen)."""
    value = table_number.strip()
    return 0 < len(value) <= GDI_LARGE_TABLE_MAX_CHARS


def split_table_meta(line: str) -> tuple[str, str]:
    """Zerlegt ``Bestell-Nr.: 9   Tisch: 4`` in linken Teil und Tischnummer."""
    left, _, right = line.partition("Tisch:")
    return left.rstrip(), right.strip()


def classify_line(line: str, index: int) -> GdiLine:
    """Ordnet eine Klartext-Zeile einem GDI-Stil zu."""
    if not line.strip():
        return GdiLine(kind=GdiLineKind.EMPTY, text=line)

    stripped = line.strip()
    if _is_separator(stripped):
        return GdiLine(kind=GdiLineKind.BODY, text=line)

    if stripped in _HEADER_TITLES or index == 1:
        return GdiLine(kind=GdiLineKind.HEADER, text=line)

    priority = parse_priority_line(stripped)
    if priority is not None:
        return GdiLine(
            kind=GdiLineKind.PRIORITY_LINE,
            text=line,
            priority_icon=priority.icon,
            priority_label=priority.label,
        )

    if (
        stripped.startswith("(")
        and stripped.endswith(")")
        and index <= 4
        and len(stripped) <= 24
    ):
        return GdiLine(kind=GdiLineKind.HEADER, text=line)

    if "Tisch:" in line and "Bestell-Nr.:" in line:
        order_part, table_number = split_table_meta(line)
        return GdiLine(
            kind=GdiLineKind.TABLE_META,
            text=line,
            order_part=order_part,
            table_number=table_number,
        )

    if stripped.startswith("[") and stripped.endswith("]"):
        return GdiLine(kind=GdiLineKind.CATEGORY, text=line)

    qty_match = _QTY_RE.match(line)
    if qty_match:
        token = qty_match.group(0)
        return GdiLine(
            kind=GdiLineKind.QTY,
            text=line,
            qty_token=token,
            rest=line[len(token) :],
        )

    return GdiLine(kind=GdiLineKind.BODY, text=line)


def _is_separator(text: str) -> bool:
    return bool(text) and set(text) <= {"=", "-"}
