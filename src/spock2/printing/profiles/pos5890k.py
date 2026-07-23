"""POS 5890K Profil (58 mm, konservativ)."""

from __future__ import annotations

from spock2.printing.profiles.base import PrinterProfile

POS5890K = PrinterProfile(
    name="pos5890k",
    paper_width_mm=58,
    dots_per_line=384,
    supports_cutter=False,
    encoding="cp850",
    line_width_chars=32,
    qr_as_bitmap=True,
    capabilities=("escpos", "qr_bitmap"),
)
