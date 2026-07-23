"""Basis-Druckerprofil: Layout- und Encoding-Hilfen."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@runtime_checkable
class PrinterProfileProto(Protocol):
    """Minimales Profil-Protokoll für Renderer/Transport."""

    name: str
    paper_width_mm: int
    dots_per_line: int
    supports_cutter: bool
    encoding: str
    line_width_chars: int

    def wrap_text(self, text: str) -> list[str]: ...

    def encode(self, text: str) -> bytes: ...


@dataclass(frozen=True, slots=True)
class PrinterProfile:
    """Konkretes Druckerprofil mit Text-Wrap und Encoding."""

    name: str
    paper_width_mm: int
    dots_per_line: int
    supports_cutter: bool
    encoding: str = "utf-8"
    line_width_chars: int = 42
    qr_as_bitmap: bool = False
    capabilities: tuple[str, ...] = field(default_factory=tuple)

    def wrap_text(self, text: str) -> list[str]:
        """Bricht Text auf ``line_width_chars`` um (Wortgrenzen bevorzugt)."""
        width = max(1, self.line_width_chars)
        if not text:
            return [""]
        out: list[str] = []
        for paragraph in text.splitlines() or [""]:
            if not paragraph:
                out.append("")
                continue
            remaining = paragraph
            while remaining:
                if len(remaining) <= width:
                    out.append(remaining)
                    break
                split_at = remaining.rfind(" ", 0, width + 1)
                if split_at <= 0:
                    split_at = width
                out.append(remaining[:split_at].rstrip())
                remaining = remaining[split_at:].lstrip()
        return out

    def encode(self, text: str) -> bytes:
        """Kodiert Text gemäß Profil-Encoding (Fehler → replace)."""
        try:
            return text.encode(self.encoding, errors="replace")
        except LookupError:
            return text.encode("utf-8", errors="replace")

    def separator(self, char: str = "=") -> str:
        return char * self.line_width_chars

    def center(self, text: str) -> str:
        width = self.line_width_chars
        if len(text) >= width:
            return text[:width]
        return text.center(width)
