"""Bon-Renderer im Alt-SPOCK-Layout (Kategoriegruppen, DE-Labels)."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from typing import Any

from spock2.domain.notes import Note
from spock2.domain.orders import Order, OrderItem
from spock2.domain.print_job import PrinterRole
from spock2.printing.profiles.base import PrinterProfile


def _parse_time(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    text = str(value).strip()
    if not text:
        return None
    try:
        if "T" in text:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
    except (TypeError, ValueError):
        return None
    return None


def _group_by_category(items: list[OrderItem]) -> OrderedDict[str, list[OrderItem]]:
    grouped: OrderedDict[str, list[OrderItem]] = OrderedDict()
    for item in items:
        category = (item.category or "").strip() or "Sonstiges"
        grouped.setdefault(category, []).append(item)
    return grouped


def _header_title(role: PrinterRole) -> str:
    if role == PrinterRole.COUNTER:
        return "THEKEN-BON"
    if role == PrinterRole.SMALL:
        return "KLEIN-BON"
    return "KÜCHEN-BON"


# ESC/POS primitives (optional path for pos5890k / raw queues)
_ESC = b"\x1b"
_GS = b"\x1d"
_INIT = _ESC + b"@"
_SELECT_CODEPAGE = _ESC + b"t"
_CODEPAGE_CP850 = b"\x02"
_CUT = _GS + b"V\x00"


class ReceiptRenderer:
    """Formatiert Bestellungen und Zettel als Klartext-Bons."""

    def format_order(
        self,
        order: Order,
        profile: PrinterProfile,
        *,
        role: PrinterRole = PrinterRole.KITCHEN,
        items: list[OrderItem] | None = None,
    ) -> str:
        """Alt-SPOCK-Layout: Header, Meta, Kategoriegruppen, Mengen/Notizen."""
        width = profile.line_width_chars
        sep = profile.separator("=")
        dash = profile.separator("-")
        title = _header_title(role)

        lines: list[str] = [
            sep,
            profile.center(title),
            sep,
        ]

        table = order.display_table()
        lines.append(f"Bestell-Nr.: {order.id}   Tisch: {table}")
        if order.waiter:
            lines.append(f"Bedienung: {order.waiter}")
        time_str = _parse_time(order.created_at)
        if time_str:
            lines.append(f"Zeit: {time_str}")
        lines.append(dash)

        use_items = items if items is not None else list(order.items)
        show_categories = role not in (PrinterRole.KITCHEN, PrinterRole.COUNTER)
        if use_items:
            grouped = _group_by_category(use_items)
            for category, group_items in grouped.items():
                if show_categories:
                    show_header = category != "Sonstiges" or len(grouped) > 1
                    if show_header:
                        lines.append("")
                        lines.append(f"[{category.upper()}]")
                        lines.append(dash)
                for item in group_items:
                    qty_line = f"{item.qty}x {item.name}"
                    lines.extend(profile.wrap_text(qty_line))
                    if item.notes:
                        note_line = f"  -> {item.notes}"
                        lines.extend(profile.wrap_text(note_line))
        else:
            lines.append("Keine Positionen")

        lines.append(sep)
        # Sicherstellen, dass nichts die Breite sprengt
        return "\n".join(self._apply_hard_wrap(lines, width))

    def format_note(self, note: Note, profile: PrinterProfile) -> str:
        """ZETTEL-Layout wie Alt-SPOCK."""
        width = profile.line_width_chars
        sep = profile.separator("=")
        dash = profile.separator("-")
        priority = str(note.priority if note.priority is not None else "normal")

        lines: list[str] = [
            sep,
            profile.center("ZETTEL"),
            profile.center(f"({priority.upper()})"),
            sep,
        ]
        time_str = _parse_time(note.timestamp)
        if time_str:
            lines.append(f"Zeit: {time_str}")
        sender = note.sender or "unbekannt"
        lines.append(f"Von: {sender}")
        lines.append(dash)
        lines.extend(profile.wrap_text(note.text or ""))
        lines.append(sep)
        return "\n".join(self._apply_hard_wrap(lines, width))

    def format_test(self, role: PrinterRole, profile: PrinterProfile) -> str:
        """Kurze Testseite für Diagnose."""
        sep = profile.separator("=")
        lines: list[str] = [
            sep,
            profile.center("SPOCK2 TEST"),
            profile.center(f"Rolle: {role.value}"),
            profile.center(f"Profil: {profile.name}"),
            sep,
            "Umlaute: äöüÄÖÜ ß",
            "Euro: 12,50 €",
            *profile.wrap_text(
                "Wrap-Test: Dies ist ein bewusst langer Satz zum Prüfen "
                "des Zeilenumbruchs auf schmalem Thermopapier."
            ),
            sep,
        ]
        return "\n".join(lines)

    def render_to_bytes(self, text: str, profile: PrinterProfile) -> bytes:
        """CUPS-Textjobs: immer UTF-8 (Umlaute/€ erhalten)."""
        _ = profile  # Profil steuert Layout; Encoding für CUPS-Text = utf-8
        return text.encode("utf-8")

    def render_escpos(self, text: str, profile: PrinterProfile) -> bytes:
        """Optionales ESC/POS für konservative Geräte (z. B. pos5890k)."""
        buf = bytearray()
        buf += _INIT
        buf += _SELECT_CODEPAGE + _CODEPAGE_CP850
        # Profil-Encoding (cp850) für deutsche Zeichen
        escpos_profile = profile
        if profile.encoding.casefold() in ("utf-8", "utf8"):
            from spock2.printing.profiles.base import PrinterProfile as PP

            escpos_profile = PP(
                name=profile.name,
                paper_width_mm=profile.paper_width_mm,
                dots_per_line=profile.dots_per_line,
                supports_cutter=profile.supports_cutter,
                encoding="cp850",
                line_width_chars=profile.line_width_chars,
                qr_as_bitmap=profile.qr_as_bitmap,
                capabilities=profile.capabilities,
            )
        buf += escpos_profile.encode(text if text.endswith("\n") else text + "\n")
        buf += b"\n\n"
        if profile.supports_cutter:
            buf += _CUT
        return bytes(buf)

    @staticmethod
    def _apply_hard_wrap(lines: list[str], width: int) -> list[str]:
        """Härtet Zeilen ab, die länger als die Papierbreite sind."""
        out: list[str] = []
        for line in lines:
            if len(line) <= width:
                out.append(line)
                continue
            # Bereits gewrappt erwartet; Fallback: hart schneiden
            remaining = line
            while remaining:
                out.append(remaining[:width])
                remaining = remaining[width:]
        return out
