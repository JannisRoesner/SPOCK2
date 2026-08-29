"""Windows-GDI-Druck für Star TSP100 (Alt-SPOCK-Look)."""

from __future__ import annotations

import contextlib
import logging
import sys
from typing import Any

from spock2.api.errors import PrintFailed
from spock2.printing.gdi_layout import (
    GDI_BASE_PT,
    GDI_FONT_FALLBACKS,
    GDI_HEADER_SCALE,
    GDI_LINE_WIDTH,
    GDI_TABLE_SCALE,
    GdiLineKind,
    classify_line,
    use_large_table_font,
)

logger = logging.getLogger(__name__)

_LOGPIXELSY = 90  # win32con.LOGPIXELSY


def gdi_available() -> bool:
    """True, wenn unter Windows win32ui+win32print importierbar sind."""
    if sys.platform != "win32":
        return False
    try:
        import win32print  # noqa: F401
        import win32ui  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def gdi_print_text(
    printer: str,
    text: str,
    job_name: str,
    *,
    line_width: int = GDI_LINE_WIDTH,
) -> None:
    """Druckt Unicode-Bon-Text per GDI über den Windows-Treiber."""
    if not printer:
        raise PrintFailed("Leerer Druckername")
    try:
        import win32ui
    except Exception as exc:  # noqa: BLE001
        raise PrintFailed("win32ui nicht verfügbar", cause=exc) from exc

    hDC: Any = None
    fonts: list[Any] = []
    try:
        hDC = win32ui.CreateDC()
        hDC.CreatePrinterDC(printer)
        hDC.StartDoc(job_name or "SPOCK2")
        try:
            hDC.StartPage()
            _render_page(hDC, win32ui, text, line_width, fonts)
            hDC.EndPage()
        finally:
            hDC.EndDoc()
    except PrintFailed:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PrintFailed(
            f"GDI-Druck an '{printer}' fehlgeschlagen",
            cause=exc,
        ) from exc
    finally:
        if hDC is not None:
            with contextlib.suppress(Exception):
                hDC.DeleteDC()
        for font in fonts:
            with contextlib.suppress(Exception):
                font.DeleteObject()

    logger.info("event=print_gdi printer=%s title=%s", printer, job_name)


def _render_page(
    hDC: Any,
    win32ui: Any,
    text: str,
    line_width: int,
    fonts: list[Any],
) -> None:
    dpi_y = _device_dpi(hDC)
    base_pt = max(6, min(14, int(GDI_BASE_PT)))
    family = _pick_font_family()
    base_height = -int(base_pt * dpi_y / 72)
    header_pt = int(base_pt * GDI_HEADER_SCALE)
    table_pt = int(base_pt * GDI_TABLE_SCALE)
    header_height = -int(header_pt * dpi_y / 72)
    table_height = -int(table_pt * dpi_y / 72)

    base_font = win32ui.CreateFont(
        {"name": family, "height": base_height, "weight": 400}
    )
    bold_font = win32ui.CreateFont(
        {"name": family, "height": base_height, "weight": 700}
    )
    header_font = win32ui.CreateFont(
        {"name": family, "height": header_height, "weight": 700}
    )
    table_font = win32ui.CreateFont(
        {"name": family, "height": table_height, "weight": 700}
    )
    fonts.extend([base_font, bold_font, header_font, table_font])

    hDC.SelectObject(base_font)
    base_h = _extent_h(hDC, base_font)
    header_h = _extent_h(hDC, header_font)
    table_h = _extent_h(hDC, table_font)
    char_w = _extent_w(hDC, base_font, "M")
    receipt_w = max(char_w * max(1, line_width), 1)

    x = 10
    y = 10
    base_spacing = int(base_h * 1.05)
    header_spacing = int(header_h * 1.05)
    table_spacing = int(table_h * 1.05)

    lines = list(text.splitlines())
    # etwas Vorschub für Cutter/Abriss
    lines.extend(["", ""])

    for idx, line in enumerate(lines):
        parsed = classify_line(line, idx)
        if parsed.kind == GdiLineKind.EMPTY:
            y += base_spacing
            continue

        if parsed.kind == GdiLineKind.HEADER:
            stripped = line.strip()
            hDC.SelectObject(header_font)
            text_w = _extent_w(hDC, header_font, stripped)
            x_centered = x + max(0, (receipt_w - text_w) // 2)
            hDC.TextOut(x_centered, y, stripped)
            y += header_spacing
            continue

        if parsed.kind == GdiLineKind.TABLE_META:
            y = _draw_table_meta(
                hDC,
                x,
                y,
                parsed.order_part,
                parsed.table_number,
                base_font,
                bold_font,
                table_font,
                receipt_w,
                base_spacing,
                table_spacing,
            )
            continue

        if parsed.kind == GdiLineKind.CATEGORY:
            hDC.SelectObject(bold_font)
            hDC.TextOut(x, y, line)
            y += base_spacing
            continue

        if parsed.kind == GdiLineKind.QTY:
            hDC.SelectObject(bold_font)
            hDC.TextOut(x, y, parsed.qty_token)
            qty_w = _extent_w(hDC, bold_font, parsed.qty_token)
            hDC.SelectObject(base_font)
            hDC.TextOut(x + qty_w, y, parsed.rest)
            y += base_spacing
            continue

        hDC.SelectObject(base_font)
        hDC.TextOut(x, y, line)
        y += base_spacing


def _draw_table_meta(
    hDC: Any,
    x: int,
    y: int,
    order_part: str,
    table_number: str,
    base_font: Any,
    bold_font: Any,
    table_font: Any,
    receipt_w: int,
    base_spacing: int,
    table_spacing: int,
) -> int:
    label = "Tisch: "
    large = use_large_table_font(table_number)
    num_font = table_font if large else bold_font

    hDC.SelectObject(base_font)
    hDC.TextOut(x, y, order_part)
    order_w = _extent_w(hDC, base_font, order_part)
    gap = _extent_w(hDC, base_font, "  ")
    label_w = _extent_w(hDC, base_font, label)

    hDC.SelectObject(num_font)
    num_w = _extent_w(hDC, num_font, table_number) if table_number else 0

    tisch_x = x + receipt_w - label_w - num_w
    min_x = x + order_w + gap
    if tisch_x < min_x:
        tisch_x = min_x

    hDC.SelectObject(base_font)
    hDC.TextOut(tisch_x, y, label)
    hDC.SelectObject(num_font)
    hDC.TextOut(tisch_x + label_w, y, table_number)

    return y + (table_spacing if large else base_spacing)


def _device_dpi(hDC: Any) -> int:
    try:
        dpi = int(hDC.GetDeviceCaps(_LOGPIXELSY))
        if dpi > 0:
            return dpi
    except Exception:  # noqa: BLE001
        pass
    return 96


def _extent_h(hDC: Any, font: Any) -> int:
    hDC.SelectObject(font)
    try:
        return int(hDC.GetTextExtent("A")[1])
    except Exception:  # noqa: BLE001
        return 16


def _extent_w(hDC: Any, font: Any, text: str) -> int:
    if not text:
        return 0
    hDC.SelectObject(font)
    try:
        return int(hDC.GetTextExtent(text)[0])
    except Exception:  # noqa: BLE001
        return max(1, len(text) * 8)


def _pick_font_family() -> str:
    return GDI_FONT_FALLBACKS[0]
