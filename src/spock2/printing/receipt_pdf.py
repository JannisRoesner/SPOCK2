"""CUPS-PDF im Alt-SPOCK-Look (große Tischnummer, keine umgebrochenen ===)."""

from __future__ import annotations

import re
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

# Courier (Standard-14): feste Zeichenbreite 600/1000 em
_COURIER_EM = 0.6
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

# Courier ist auf Thermopapier sehr dünn: Glyphen zusätzlich konturieren
# (Textmodus 2 = füllen + stricheln) statt nur füllen.
_TEXT_STROKE_RATIO = 0.035
_TEXT_STROKE_MIN_PT = 0.20
_TEXT_STROKE_MAX_PT = 0.55
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
class ReceiptLayout:
    page_w: float
    page_h: float
    base_pt: float
    header_pt: float
    table_pt: float
    ops: tuple[TextOp | RuleOp, ...] = field(default_factory=tuple)


def layout_receipt(
    text: str,
    *,
    page_width_pt: int,
    line_width: int = GDI_LINE_WIDTH,
) -> ReceiptLayout:
    """Punkt-Layout analog zum Windows-GDI-Bon.

    ``page_width_pt`` ist die **bedruckbare** Breite (``profile.printable_width_pt``),
    nicht die Rollenbreite. Seitenmaße bleiben ganzzahlig, damit die
    CUPS-Media-Option exakt der MediaBox entspricht.
    """
    page_w = float(max(72, int(page_width_pt)))
    usable = max(1.0, page_w - 2 * _MARGIN_PT)
    base_pt = min(float(GDI_BASE_PT), usable / (max(1, line_width) * _COURIER_EM))
    header_pt = base_pt * GDI_HEADER_SCALE
    table_pt = base_pt * GDI_TABLE_SCALE
    base_lead = base_pt * 1.2
    header_lead = header_pt * 1.15
    table_lead = table_pt * 1.05

    ops: list[TextOp | RuleOp] = []
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
            text_w = _text_width(stripped, header_pt)
            x = _MARGIN_PT + max(0.0, (usable - text_w) / 2.0)
            ops.append(TextOp(x=x, y_top=y, size=header_pt, bold=True, text=stripped))
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
                    x=_MARGIN_PT + _text_width(parsed.qty_token, base_pt),
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
    """Erzeugt ein einseitiges PDF (Courier) für CUPS/Star-Raster."""
    layout = layout_receipt(text, page_width_pt=page_width_pt, line_width=line_width)
    stream = _content_stream(layout)
    return _assemble_pdf(layout.page_w, layout.page_h, stream)


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
    ops: list[TextOp | RuleOp],
    *,
    y: float,
    order_part: str,
    table_number: str,
    base_pt: float,
    table_pt: float,
    usable: float,
    base_lead: float,
    table_lead: float,
) -> float:
    large = use_large_table_font(table_number)
    num_pt = table_pt if large else base_pt
    label = "Tisch: "
    ops.append(TextOp(x=_MARGIN_PT, y_top=y, size=base_pt, bold=False, text=order_part))

    order_w = _text_width(order_part, base_pt)
    gap = _text_width("  ", base_pt)
    label_w = _text_width(label, base_pt)
    num_w = _text_width(table_number, num_pt) if table_number else 0.0
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


def _text_width(text: str, size: float) -> float:
    return len(text) * size * _COURIER_EM


def _text_stroke_width(size: float) -> float:
    """Konturbreite, die Courier auf Thermopapier lesbar fett macht."""
    return min(_TEXT_STROKE_MAX_PT, max(_TEXT_STROKE_MIN_PT, size * _TEXT_STROKE_RATIO))


def _content_stream(layout: ReceiptLayout) -> bytes:
    buf = bytearray()
    right = layout.page_w - _MARGIN_PT
    for op in layout.ops:
        if isinstance(op, RuleOp):
            y1 = layout.page_h - op.y
            buf += f"{_RULE_WIDTH_PT:.2f} w\n".encode("ascii")
            buf += f"{_MARGIN_PT:.2f} {y1:.2f} m {right:.2f} {y1:.2f} l S\n".encode("ascii")
            if op.double:
                y2 = y1 - 2.4
                buf += f"{_MARGIN_PT:.2f} {y2:.2f} m {right:.2f} {y2:.2f} l S\n".encode("ascii")
            continue
        pdf_y = layout.page_h - op.y_top - op.size
        font = b"/F2" if op.bold else b"/F1"
        buf += b"BT "
        buf += font
        buf += f" {op.size:.2f} Tf 2 Tr {_text_stroke_width(op.size):.2f} w ".encode("ascii")
        buf += f"1 0 0 1 {op.x:.2f} {pdf_y:.2f} Tm ".encode("ascii")
        buf += _pdf_literal(op.text)
        buf += b" Tj ET\n"
    return bytes(buf)


def _pdf_literal(text: str) -> bytes:
    raw = text.encode("cp1252", errors="replace")
    escaped = raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + escaped + b")"


def _assemble_pdf(page_w: float, page_h: float, stream: bytes) -> bytes:
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w:.0f} {page_h:.0f}] "
            f"/CropBox [0 0 {page_w:.0f} {page_h:.0f}] /Rotate 0 "
            f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>"
        ).encode("ascii"),
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>",
    ]

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
