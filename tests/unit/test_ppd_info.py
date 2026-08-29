"""Tests für die PPD-Geometrie-Erkennung."""

from __future__ import annotations

from spock2.printing.ppd_info import parse_ppd_geometry
from spock2.printing.profiles.tsp100 import TSP100
from spock2.printing.receipt_pdf import layout_receipt

# Auszug aus einer echten starcupsdrv-PPD (TSP100, 72 mm Druckbreite).
STAR_PPD = """*PPD-Adobe: "4.3"
*ModelName: "Star TSP100 Cutter (TSP143)"
*NickName: "Star TSP100 Cutter (TSP143)"
*LandscapeOrientation: Plus90
*VariablePaperSize: True
*TTRasterizer: Type42
*DefaultPageSize: SELECTPAPERXXMM
*PageSize SELECTPAPERXXMM/Custom Paper Size(72mm * 297mm): "
      <</PageSize[204 842]/ImagingBBox null>>
      setpagedevice"
*PageSize 72X200MM/72mm x 200mm: "
      <</PageSize[204 567]/ImagingBBox null>>
      setpagedevice"
*MaxMediaWidth:  "204"
*MaxMediaHeight: "23219"
*HWMargins:  0 0 0 0
*CustomPageSize True: "pop pop pop <</PageSize[5 -2 roll]/ImagingBBox null>>setpagedevice"
*ParamCustomPageSize Width:        1 points 72 204
*ParamCustomPageSize Height:       2 points 72 23219
*ParamCustomPageSize WidthOffset:  3 points 0 0
*ParamCustomPageSize HeightOffset: 4 points 0 0
*ParamCustomPageSize Orientation:  5 int 0 0
"""

# Generische IPP-Everywhere-Queue: A4, keine variablen Formate.
EVERYWHERE_PPD = """*PPD-Adobe: "4.3"
*NickName: "spock-kitchen, driverless, cups-filters"
*DefaultPageSize: A4
*PageSize A4/A4: "<</PageSize[595 842]/ImagingBBox null>>setpagedevice"
*HWMargins: 8 8 8 8
"""


def test_star_ppd_allows_variable_receipt_length() -> None:
    geo = parse_ppd_geometry(STAR_PPD)
    assert geo.nickname == "Star TSP100 Cutter (TSP143)"
    assert geo.default_page_size == "SELECTPAPERXXMM"
    assert geo.variable_paper_size is True
    assert geo.supports_custom_size is True
    assert geo.width_range_pt == (72.0, 204.0)
    assert geo.height_range_pt == (72.0, 23219.0)
    assert geo.hw_margins_pt == (0.0, 0.0, 0.0, 0.0)
    assert "72X200MM" in geo.page_sizes


def test_star_ppd_accepts_our_pages_but_not_roll_width() -> None:
    geo = parse_ppd_geometry(STAR_PPD)
    assert geo.rejects(204.0, 300.0) is None
    # 80 mm = 227 pt: genau der Fehler, den die Rollenbreite verursacht hätte.
    reason = geo.rejects(226.77, 300.0)
    assert reason is not None and "Breite" in reason


def test_star_ppd_rejects_absurd_length() -> None:
    geo = parse_ppd_geometry(STAR_PPD)
    reason = geo.rejects(204.0, 99999.0)
    assert reason is not None and "Länge" in reason


def test_everywhere_ppd_has_no_custom_size() -> None:
    geo = parse_ppd_geometry(EVERYWHERE_PPD)
    assert geo.variable_paper_size is False
    assert geo.supports_custom_size is False
    reason = geo.rejects(204.0, 300.0)
    assert reason is not None and "Custom" in reason


def test_real_bon_geometry_fits_star_ppd() -> None:
    """Alle realistischen Bonlängen liegen in den PPD-Grenzen."""
    geo = parse_ppd_geometry(STAR_PPD)
    for lines in (1, 10, 50, 200):
        text = "\n".join(["=" * 32, "KÜCHEN-BON".center(32), "=" * 32] + ["1x Test"] * lines)
        layout = layout_receipt(text, page_width_pt=TSP100.printable_width_pt)
        assert geo.rejects(layout.page_w, layout.page_h) is None
