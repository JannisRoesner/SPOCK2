"""Prüft, ob eine CUPS-Queue variable Bonlängen erlaubt.

Beantwortet die Frage „packt CUPS meinen Bon in eine fixe Länge?“ mit den
echten Werten aus der PPD statt mit Vermutungen.
"""

from __future__ import annotations

import argparse
import sys

from spock2.config.loader import load_config
from spock2.domain.orders import Order, OrderItem
from spock2.domain.print_job import PrinterRole
from spock2.printing.cups_transport import CupsTransport, cups_available, cups_job_options
from spock2.printing.gdi_layout import gdi_layout_profile
from spock2.printing.ppd_info import PpdGeometry
from spock2.printing.profiles import get_profile
from spock2.printing.receipt_pdf import layout_receipt, render_receipt_pdf
from spock2.printing.renderer import ReceiptRenderer

_PT_TO_MM = 25.4 / 72.0


def _fmt_range(rng: tuple[float, float] | None) -> str:
    if rng is None:
        return "—"
    low, high = rng
    return f"{low:.0f}–{high:.0f} pt ({low * _PT_TO_MM:.1f}–{high * _PT_TO_MM:.1f} mm)"


def _report_ppd(geo: PpdGeometry) -> None:
    print("PPD:")
    print(f"  Modell:              {geo.nickname or '—'}")
    print(f"  DefaultPageSize:     {geo.default_page_size or '—'}")
    print(f"  VariablePaperSize:   {'ja' if geo.variable_paper_size else 'NEIN'}")
    print(f"  Custom-Breite:       {_fmt_range(geo.width_range_pt)}")
    print(f"  Custom-Länge:        {_fmt_range(geo.height_range_pt)}")
    if geo.hw_margins_pt:
        left, bottom, right, top = geo.hw_margins_pt
        print(
            f"  HWMargins:           l={left:.0f} b={bottom:.0f} "
            f"r={right:.0f} t={top:.0f} pt"
        )
    if geo.page_sizes:
        shown = ", ".join(geo.page_sizes[:8])
        more = f" (+{len(geo.page_sizes) - 8})" if len(geo.page_sizes) > 8 else ""
        print(f"  Feste Formate:       {shown}{more}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="spock2-probe-queue",
        description="Zeigt die PPD-Seitengrenzen einer CUPS-Queue und prüft, "
        "ob die Bon-PDFs von SPOCK2 hineinpassen.",
    )
    parser.add_argument(
        "--role",
        choices=["kitchen", "counter", "small"],
        default="kitchen",
        help="Druckerrolle (Default: kitchen)",
    )
    parser.add_argument("--queue", default=None, help="Queue-Name (sonst aus Config)")
    parser.add_argument(
        "--config", default=None, help="Pfad zur TOML-Config (sonst SPOCK2_CONFIG)"
    )
    parser.add_argument(
        "--items",
        type=int,
        nargs="*",
        default=[1, 5, 20],
        help="Bon-Längen (Positionsanzahl), die geprüft werden",
    )
    args = parser.parse_args(argv)

    if not cups_available():
        print("pycups nicht verfügbar – nur unter Linux/CUPS nutzbar.", file=sys.stderr)
        return 1

    cfg = load_config(args.config, allow_missing=True)
    role = PrinterRole(args.role)
    printer = cfg.printer_for_role(role.value)  # type: ignore[arg-type]
    queue = args.queue or (printer.queue if printer else f"spock-{role.value}")
    profile = gdi_layout_profile(
        get_profile(printer.profile if printer else "tsp100")
    )

    try:
        transport = CupsTransport()
    except Exception as exc:  # noqa: BLE001
        print(f"CUPS nicht erreichbar: {exc}", file=sys.stderr)
        return 1

    print(f"Queue:   {queue}")
    print(f"Profil:  {profile.name}  Rolle={profile.paper_width_mm} mm")
    print(f"Druckbreite: {profile.printable_width_pt} pt "
          f"({profile.printable_width_pt * _PT_TO_MM:.1f} mm)")
    print()

    geo = transport.get_ppd_geometry(queue)
    if geo is None:
        print("Keine PPD lesbar – Raw-Queue? Dann filtert CUPS nicht und ein PDF")
        print("wird als Rohdaten gedruckt. Queue mit Hersteller-PPD neu anlegen.")
        return 2
    _report_ppd(geo)
    print()

    print("Bon-Geometrie (was SPOCK2 anfordern würde):")
    renderer = ReceiptRenderer()
    problems = 0
    for count in args.items:
        order = Order(
            id=99,
            table_number=1,
            waiter="Probe",
            items=[
                OrderItem(qty=1, name=f"Position {i}", category="Speisen")
                for i in range(count)
            ],
        )
        text = renderer.format_order(order, profile, role=role)
        layout = layout_receipt(
            text,
            page_width_pt=profile.printable_width_pt,
            line_width=profile.line_width_chars,
        )
        pdf = render_receipt_pdf(
            text,
            page_width_pt=profile.printable_width_pt,
            line_width=profile.line_width_chars,
        )
        media = cups_job_options(pdf).get("media", "—")
        reason = geo.rejects(layout.page_w, layout.page_h)
        status = "OK" if reason is None else f"PROBLEM: {reason}"
        if reason is not None:
            problems += 1
        print(
            f"  {count:3d} Positionen -> {layout.page_h * _PT_TO_MM:6.1f} mm  "
            f"media={media:<20s} {status}"
        )

    print()
    if problems:
        print("Mindestens eine Bonlänge passt nicht in die PPD-Grenzen.")
        print("SPOCK2 fällt dann auf einen Job ohne Geometrie-Optionen zurück –")
        print("der Bon kommt gedreht oder gestaucht heraus.")
        return 2

    if geo.default_page_size and geo.supports_custom_size:
        print(f"Alles innerhalb der PPD-Grenzen. DefaultPageSize "
              f"({geo.default_page_size}) wird pro Job überschrieben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
