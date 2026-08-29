"""Star TSP100 Profil (80 mm)."""

from __future__ import annotations

from spock2.printing.profiles.base import PrinterProfile

TSP100 = PrinterProfile(
    name="tsp100",
    paper_width_mm=80,
    dots_per_line=576,
    supports_cutter=True,
    # CUPS: PDF (GDI-Look); Windows: GDI; ESC/POS-Fallback cp850
    encoding="utf-8",
    line_width_chars=42,
    qr_as_bitmap=False,
    capabilities=("cutter", "barcode", "cups_text", "gdi"),
)

# Alias für ESC/POS-Rohpfad (deutsche Umlaute)
TSP100_ESCPOS = PrinterProfile(
    name="tsp100",
    paper_width_mm=80,
    dots_per_line=576,
    supports_cutter=True,
    encoding="cp850",
    line_width_chars=42,
    qr_as_bitmap=False,
    capabilities=("cutter", "barcode", "escpos"),
)
