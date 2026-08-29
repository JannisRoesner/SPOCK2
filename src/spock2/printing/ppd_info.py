"""PPD-Geometrie lesen: erlaubt die Queue variable Bonlängen?

Der Bon-PDF-Pfad steht und fällt damit, dass CUPS ``media=Custom.<B>x<H>``
akzeptiert. Die Grenzen dafür stehen in der PPD der Queue, nicht in SPOCK2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# *ParamCustomPageSize Width: 1 points 72 204
_PARAM_RE = re.compile(
    r"^\*ParamCustomPageSize\s+(Width|Height)\s*:\s*\d+\s+(\S+)\s+([\d.]+)\s+([\d.]+)",
    re.MULTILINE,
)
_NICKNAME_RE = re.compile(r'^\*(?:NickName|ModelName)\s*:\s*"?([^"\n]+)"?', re.MULTILINE)
_DEFAULT_SIZE_RE = re.compile(r"^\*DefaultPageSize\s*:\s*(\S+)", re.MULTILINE)
_VARIABLE_RE = re.compile(r"^\*VariablePaperSize\s*:\s*(\w+)", re.MULTILINE)
_HW_MARGINS_RE = re.compile(
    r"^\*HWMargins\s*:\s*\"?\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", re.MULTILINE
)
_PAGE_SIZE_RE = re.compile(r"^\*PageSize\s+([^/:\s]+)", re.MULTILINE)
_MAX_WIDTH_RE = re.compile(r'^\*MaxMediaWidth\s*:\s*"?([\d.]+)', re.MULTILINE)
_MAX_HEIGHT_RE = re.compile(r'^\*MaxMediaHeight\s*:\s*"?([\d.]+)', re.MULTILINE)


@dataclass(frozen=True, slots=True)
class PpdGeometry:
    """Für SPOCK2 relevante Teile einer PPD."""

    nickname: str = ""
    default_page_size: str = ""
    variable_paper_size: bool = False
    width_range_pt: tuple[float, float] | None = None
    height_range_pt: tuple[float, float] | None = None
    hw_margins_pt: tuple[float, float, float, float] | None = None
    page_sizes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def supports_custom_size(self) -> bool:
        return self.variable_paper_size and self.width_range_pt is not None

    def rejects(self, width_pt: float, height_pt: float) -> str | None:
        """Grund, warum ``Custom.<width>x<height>`` scheitern würde – sonst None."""
        if not self.supports_custom_size:
            return "PPD kennt keine Custom-Seitengröße (VariablePaperSize fehlt)"
        assert self.width_range_pt is not None
        w_min, w_max = self.width_range_pt
        if not w_min <= width_pt <= w_max:
            return (
                f"Breite {width_pt:.0f} pt außerhalb {w_min:.0f}–{w_max:.0f} pt "
                f"({width_pt * 25.4 / 72:.1f} mm vs. {w_max * 25.4 / 72:.1f} mm max)"
            )
        if self.height_range_pt is not None:
            h_min, h_max = self.height_range_pt
            if not h_min <= height_pt <= h_max:
                return (
                    f"Länge {height_pt:.0f} pt außerhalb {h_min:.0f}–{h_max:.0f} pt "
                    f"({height_pt * 25.4 / 72:.1f} mm vs. {h_max * 25.4 / 72:.1f} mm max)"
                )
        return None


def _to_points(value: float, unit: str) -> float:
    unit = unit.strip().casefold()
    if unit == "mm":
        return value * 72.0 / 25.4
    if unit == "cm":
        return value * 720.0 / 25.4
    if unit in {"in", "inch"}:
        return value * 72.0
    return value  # points


def parse_ppd_geometry(text: str) -> PpdGeometry:
    """Liest Nickname, Default-Format und Custom-Grenzen aus einem PPD-Text."""
    ranges: dict[str, tuple[float, float]] = {}
    for name, unit, low, high in _PARAM_RE.findall(text):
        try:
            ranges[name] = (_to_points(float(low), unit), _to_points(float(high), unit))
        except ValueError:
            continue

    # Ältere PPDs führen nur MaxMediaWidth/Height.
    if "Width" not in ranges:
        max_w = _MAX_WIDTH_RE.search(text)
        if max_w:
            ranges["Width"] = (0.0, float(max_w.group(1)))
    if "Height" not in ranges:
        max_h = _MAX_HEIGHT_RE.search(text)
        if max_h:
            ranges["Height"] = (0.0, float(max_h.group(1)))

    variable = _VARIABLE_RE.search(text)
    margins = _HW_MARGINS_RE.search(text)
    nickname = _NICKNAME_RE.search(text)
    default_size = _DEFAULT_SIZE_RE.search(text)

    return PpdGeometry(
        nickname=nickname.group(1).strip() if nickname else "",
        default_page_size=default_size.group(1).strip() if default_size else "",
        variable_paper_size=bool(variable)
        and variable.group(1).strip().casefold() in {"true", "yes"},
        width_range_pt=ranges.get("Width"),
        height_range_pt=ranges.get("Height"),
        hw_margins_pt=(
            tuple(float(margins.group(i)) for i in (1, 2, 3, 4))  # type: ignore[misc]
            if margins
            else None
        ),
        page_sizes=tuple(dict.fromkeys(_PAGE_SIZE_RE.findall(text))),
    )
