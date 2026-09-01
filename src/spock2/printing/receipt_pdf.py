"""CUPS-PDF im Alt-SPOCK-Look (große Tischnummer, keine umgebrochenen ===)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from math import ceil

from spock2.printing.gdi_layout import (
    GDI_BASE_PT,
    GDI_HEADER_SCALE,
    GDI_LINE_WIDTH,
    GDI_TABLE_SCALE,
    GdiLineKind,
    classify_line,
    use_large_table_font,
)
from spock2.printing.receipt_fonts import ReceiptPdfFonts, build_receipt_fonts

# Sans-Monospace (JetBrains Mono, wie Consolas unter Windows-GDI).
_MONO_EM = 0.6

_MM_TO_PT = 72.0 / 25.4

# Star-PPD: ``HWMargins: 0 0 0 0`` – die 204 pt sind voll bedruckbar. Der Rand
# ist reine Optik. 32 Zeichen à 10 pt brauchen exakt 192 pt, passt also.
_MARGIN_PT = 6.0

# Vorschub nach der letzten Zeile, damit der Abriss nicht in den Text läuft.
_FEED_PT = 8.0 * _MM_TO_PT

# pdftopdf dreht querformatige Seiten auf das Medium. Die Seite muss daher
# hochkant bleiben, auch wenn der Inhalt kürzer als die Breite ist – sonst
# kommt der Bon um 90° gedreht quer aus der Rolle. Kleinster sicherer Wert,
# damit die Rollenlänge weiter dem Inhalt folgt.
_MIN_PAGE_ASPECT = 1.05

# Trennlinien etwas kräftiger als Fließtext.
_RULE_WIDTH_PT = 1.0

_MEDIABOX_RE = re.compile(
    rb"/MediaBox\s*\[\s*([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s*\]"
)


@dataclass(frozen=True, slots=True)
class TextOp:
    x: float
    y_top: float
    size: float
    bold: bool
    text: str


@dataclass(frozen=True, slots=True)
class RuleOp:
    y: float
    double: bool


@dataclass(frozen=True, slots=True)
class IconOp:
    kind: str  # ``warning`` | ``siren``
    x_center: float
    y_top: float
    size: float


@dataclass(frozen=True, slots=True)
class ReceiptLayout:
    page_w: float
    page_h: float
    base_pt: float
    header_pt: float
    table_pt: float
    ops: tuple[TextOp | RuleOp | IconOp, ...] = field(default_factory=tuple)


def layout_receipt(
    text: str,
    *,
    page_width_pt: int,
    line_width: int = GDI_LINE_WIDTH,
    fonts: ReceiptPdfFonts | None = None,
) -> ReceiptLayout:
    """Punkt-Layout analog zum Windows-GDI-Bon.

    ``page_width_pt`` ist die **bedruckbare** Breite (``profile.printable_width_pt``),
    nicht die Rollenbreite. Seitenmaße bleiben ganzzahlig, damit die
    CUPS-Media-Option exakt der MediaBox entspricht.
    """
    page_w = float(max(72, int(page_width_pt)))
    usable = max(1.0, page_w - 2 * _MARGIN_PT)
    mono_em = fonts.mono_em if fonts is not None else _MONO_EM
    width_fn = fonts.text_width if fonts is not None else _fallback_text_width
    base_pt = min(float(GDI_BASE_PT), usable / (max(1, line_width) * mono_em))
    header_pt = base_pt * GDI_HEADER_SCALE
    table_pt = base_pt * GDI_TABLE_SCALE
    base_lead = base_pt * 1.2
    header_lead = header_pt * 1.15
    table_lead = table_pt * 1.05

    ops: list[TextOp | RuleOp | IconOp] = []
    y = _MARGIN_PT
    lines = list(text.splitlines())
    lines.extend(["", ""])

    for idx, line in enumerate(lines):
        parsed = classify_line(line, idx)
        if parsed.kind == GdiLineKind.EMPTY:
            y += base_lead
            continue

        if _is_rule_line(line):
            ops.append(RuleOp(y=y + base_pt * 0.45, double="=" in line.strip()[:1]))
            y += base_lead
            continue

        if parsed.kind == GdiLineKind.HEADER:
            stripped = line.strip()
            text_w = width_fn(stripped, header_pt)
            x = _MARGIN_PT + max(0.0, (usable - text_w) / 2.0)
            ops.append(TextOp(x=x, y_top=y, size=header_pt, bold=True, text=stripped))
            y += header_lead
            continue

        if parsed.kind == GdiLineKind.PRIORITY_LINE:
            icon_pt = header_pt * 1.15
            label_pt = header_pt
            gap = width_fn("  ", label_pt)
            label = parsed.priority_label
            label_w = width_fn(label, label_pt)
            icon_kind = parsed.priority_icon or "warning"
            if icon_kind == "siren":
                icon_w = icon_pt * 0.95
            else:
                icon_w = width_fn("\u26a0", icon_pt)
            total_w = icon_w + gap + label_w + gap + icon_w
            x = _MARGIN_PT + max(0.0, (usable - total_w) / 2.0)
            if icon_kind == "siren":
                ops.append(
                    IconOp(kind="siren", x_center=x + icon_w / 2.0, y_top=y, size=icon_pt)
                )
                ops.append(
                    TextOp(
                        x=x + icon_w + gap,
                        y_top=y,
                        size=label_pt,
                        bold=True,
                        text=label,
                    )
                )
                ops.append(
                    IconOp(
                        kind="siren",
                        x_center=x + icon_w + gap + label_w + gap + icon_w / 2.0,
                        y_top=y,
                        size=icon_pt,
                    )
                )
            else:
                ops.append(
                    TextOp(x=x, y_top=y, size=icon_pt, bold=True, text="\u26a0")
                )
                ops.append(
                    TextOp(
                        x=x + icon_w + gap,
                        y_top=y,
                        size=label_pt,
                        bold=True,
                        text=label,
                    )
                )
                ops.append(
                    TextOp(
                        x=x + icon_w + gap + label_w + gap,
                        y_top=y,
                        size=icon_pt,
                        bold=True,
                        text="\u26a0",
                    )
                )
            y += header_lead
            continue

        if parsed.kind == GdiLineKind.TABLE_META:
            y = _layout_table_meta(
                ops,
                y=y,
                order_part=parsed.order_part,
                table_number=parsed.table_number,
                base_pt=base_pt,
                table_pt=table_pt,
                usable=usable,
                base_lead=base_lead,
                table_lead=table_lead,
                width_fn=width_fn,
            )
            continue

        if parsed.kind == GdiLineKind.CATEGORY:
            ops.append(TextOp(x=_MARGIN_PT, y_top=y, size=base_pt, bold=True, text=line.rstrip()))
            y += base_lead
            continue

        if parsed.kind == GdiLineKind.QTY:
            ops.append(
                TextOp(x=_MARGIN_PT, y_top=y, size=base_pt, bold=True, text=parsed.qty_token)
            )
            ops.append(
                TextOp(
                    x=_MARGIN_PT + width_fn(parsed.qty_token, base_pt),
                    y_top=y,
                    size=base_pt,
                    bold=False,
                    text=parsed.rest,
                )
            )
            y += base_lead
            continue

        ops.append(TextOp(x=_MARGIN_PT, y_top=y, size=base_pt, bold=False, text=line.rstrip()))
        y += base_lead

    page_h = float(ceil(max(page_w * _MIN_PAGE_ASPECT, y + _MARGIN_PT + _FEED_PT)))
    return ReceiptLayout(
        page_w=page_w,
        page_h=page_h,
        base_pt=base_pt,
        header_pt=header_pt,
        table_pt=table_pt,
        ops=tuple(ops),
    )


def render_receipt_pdf(
    text: str,
    *,
    page_width_pt: int,
    line_width: int = GDI_LINE_WIDTH,
) -> bytes:
    """Erzeugt ein einseitiges PDF (eingebettete Monospace-Schrift) für CUPS."""
    fonts = build_receipt_fonts(text)
    layout = layout_receipt(
        text, page_width_pt=page_width_pt, line_width=line_width, fonts=fonts
    )
    stream = _content_stream(layout, fonts)
    return _assemble_pdf(layout.page_w, layout.page_h, stream, fonts)


def pdf_media_size_pt(data: bytes) -> tuple[float, float] | None:
    """Seitengröße (Breite, Höhe) in Punkten aus der ersten ``/MediaBox``."""
    match = _MEDIABOX_RE.search(data)
    if match is None:
        return None
    try:
        x0, y0, x1, y1 = (float(match.group(i)) for i in (1, 2, 3, 4))
    except ValueError:
        return None
    width = abs(x1 - x0)
    height = abs(y1 - y0)
    if width <= 0 or height <= 0:
        return None
    return width, height


def _layout_table_meta(
    ops: list[TextOp | RuleOp | IconOp],
    *,
    y: float,
    order_part: str,
    table_number: str,
    base_pt: float,
    table_pt: float,
    usable: float,
    base_lead: float,
    table_lead: float,
    width_fn: Callable[[str, float], float],
) -> float:
    large = use_large_table_font(table_number)
    num_pt = table_pt if large else base_pt
    label = "Tisch: "
    ops.append(TextOp(x=_MARGIN_PT, y_top=y, size=base_pt, bold=False, text=order_part))

    order_w = width_fn(order_part, base_pt)
    gap = width_fn("  ", base_pt)
    label_w = width_fn(label, base_pt)
    num_w = width_fn(table_number, num_pt) if table_number else 0.0
    tisch_x = _MARGIN_PT + usable - label_w - num_w
    min_x = _MARGIN_PT + order_w + gap
    if tisch_x < min_x:
        tisch_x = min_x

    ops.append(TextOp(x=tisch_x, y_top=y, size=base_pt, bold=False, text=label))
    ops.append(TextOp(x=tisch_x + label_w, y_top=y, size=num_pt, bold=True, text=table_number))
    return y + (table_lead if large else base_lead)


def _is_rule_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and set(stripped) <= {"=", "-"}


def _fallback_text_width(text: str, size: float) -> float:
    return len(text) * size * _MONO_EM


def _content_stream(layout: ReceiptLayout, fonts: ReceiptPdfFonts) -> bytes:
    buf = bytearray()
    right = layout.page_w - _MARGIN_PT
    for op in layout.ops:
        if isinstance(op, IconOp):
            _append_priority_icon(buf, op, page_h=layout.page_h)
            continue
        if isinstance(op, RuleOp):
            y1 = layout.page_h - op.y
            buf += f"{_RULE_WIDTH_PT:.2f} w\n".encode("ascii")
            buf += f"{_MARGIN_PT:.2f} {y1:.2f} m {right:.2f} {y1:.2f} l S\n".encode("ascii")
            if op.double:
                y2 = y1 - 2.4
                buf += f"{_MARGIN_PT:.2f} {y2:.2f} m {right:.2f} {y2:.2f} l S\n".encode("ascii")
            continue
        pdf_y = layout.page_h - op.y_top - op.size
        face = fonts.bold if op.bold else fonts.regular
        buf += b"BT "
        buf += face.resource_name.encode("ascii")
        buf += f" {op.size:.2f} Tf 1 0 0 1 {op.x:.2f} {pdf_y:.2f} Tm ".encode("ascii")
        buf += face.pdf_hex_text(op.text)
        buf += b" Tj ET\n"
    return bytes(buf)


def _append_priority_icon(buf: bytearray, op: IconOp, *, page_h: float) -> None:
    """Vektor-Sirene für ``dringend`` (Warnung nutzt ⚠ als TextOp)."""
    if op.kind != "siren":
        return
    s = op.size
    cx = op.x_center
    y_bottom = page_h - op.y_top - s
    base_w = s * 0.62
    base_h = s * 0.2
    dome_r = s * 0.3
    base_y = y_bottom
    dome_cy = base_y + base_h + dome_r * 0.9

    buf += b"q\n"
    buf += b"0 g\n"
    # Sockel
    buf += f"{cx - base_w / 2:.2f} {base_y:.2f} {base_w:.2f} {base_h:.2f} re f\n".encode(
        "ascii"
    )
    # Kuppel
    buf += f"{cx:.2f} {dome_cy:.2f} {dome_r:.2f} 0 360 arc f\n".encode("ascii")
    # Lichtstrahlen
    buf += f"{max(1.0, s * 0.08):.2f} w\n".encode("ascii")
    ray_base = dome_cy + dome_r
    for offset in (-0.45, 0.0, 0.45):
        x0 = cx + offset * dome_r
        x1 = cx + offset * dome_r * 1.55
        y1 = ray_base + dome_r * 0.65
        buf += f"{x0:.2f} {ray_base:.2f} m {x1:.2f} {y1:.2f} l S\n".encode("ascii")
    buf += b"Q\n"


def _assemble_pdf(
    page_w: float, page_h: float, stream: bytes, fonts: ReceiptPdfFonts
) -> bytes:
    page_dict = (
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w:.0f} {page_h:.0f}] "
        f"/CropBox [0 0 {page_w:.0f} {page_h:.0f}] /Rotate 0 "
        f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 10 0 R >> >> >>"
    ).encode("ascii")
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        page_dict,
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    objects.extend(fonts.regular.pdf_objects)
    objects.extend(fonts.bold.pdf_objects)

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("ascii")
        out += body
        out += b"\nendobj\n"

    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)
