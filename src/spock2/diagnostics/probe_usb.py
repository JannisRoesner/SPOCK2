"""USB-Diagnose-CLI: Serials für CUPS/udev-Zuordnung."""

from __future__ import annotations

import argparse
import platform
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UsbDeviceInfo:
    bus: str
    address: str
    vendor_id: str
    product_id: str
    manufacturer: str
    product: str
    serial: str
    source: str


# Bekannte Thermodrucker (Vendor, Product) — nur Hinweis, kein Filter-Zwang
KNOWN_PRINTERS: dict[tuple[int, int], str] = {
    (0x0519, 0x0003): "Star TSP100 (approx)",
    (0x0519, 0x0001): "Star Micronics",
    (0x0416, 0x5011): "POS58 / Zijiang / CT-S310II",
    (0x04B8, 0x0E15): "Epson TM-T20",
    (0x04B8, 0x0202): "Epson TM-T88",
}


def _probe_pyusb(*, verbose: bool = False) -> list[UsbDeviceInfo]:
    try:
        import usb.core  # type: ignore[import-untyped]
        import usb.util  # type: ignore[import-untyped]
    except ImportError:
        if verbose:
            print("pyusb nicht installiert – überspringe pyusb-Probe.", file=sys.stderr)
        return []

    found: list[UsbDeviceInfo] = []
    try:
        devices = list(usb.core.find(find_all=True) or [])
    except Exception as exc:  # noqa: BLE001
        print(f"pyusb Fehler: {exc}", file=sys.stderr)
        return []

    for dev in devices:
        try:
            vid = int(dev.idVendor)
            pid = int(dev.idProduct)
        except Exception:  # noqa: BLE001
            continue

        def _safe_str(index: int | None, device: object = dev) -> str:
            if not index:
                return ""
            try:
                return str(usb.util.get_string(device, index) or "")
            except Exception:  # noqa: BLE001
                return ""

        manufacturer = _safe_str(getattr(dev, "iManufacturer", None))
        product = _safe_str(getattr(dev, "iProduct", None))
        serial = _safe_str(getattr(dev, "iSerialNumber", None))
        found.append(
            UsbDeviceInfo(
                bus=str(getattr(dev, "bus", "")),
                address=str(getattr(dev, "address", "")),
                vendor_id=f"{vid:04x}",
                product_id=f"{pid:04x}",
                manufacturer=manufacturer,
                product=product,
                serial=serial,
                source="pyusb",
            )
        )
    return found


def _probe_sysfs(*, verbose: bool = False) -> list[UsbDeviceInfo]:
    root = Path("/sys/bus/usb/devices")
    if not root.is_dir():
        if verbose:
            print("Kein /sys/bus/usb/devices (nicht Linux?).", file=sys.stderr)
        return []

    found: list[UsbDeviceInfo] = []
    for entry in sorted(root.iterdir()):
        vid_path = entry / "idVendor"
        pid_path = entry / "idProduct"
        if not vid_path.is_file() or not pid_path.is_file():
            continue

        def _read(name: str, base: Path = entry) -> str:
            p = base / name
            if not p.is_file():
                return ""
            try:
                return p.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                return ""

        found.append(
            UsbDeviceInfo(
                bus=_read("busnum"),
                address=_read("devnum"),
                vendor_id=_read("idVendor"),
                product_id=_read("idProduct"),
                manufacturer=_read("manufacturer"),
                product=_read("product"),
                serial=_read("serial"),
                source="sysfs",
            )
        )
    return found


def collect_devices(*, verbose: bool = False) -> list[UsbDeviceInfo]:
    devices = _probe_pyusb(verbose=verbose)
    if not devices:
        devices = _probe_sysfs(verbose=verbose)
    return devices


def _hint_known(vid: str, pid: str) -> str:
    try:
        key = (int(vid, 16), int(pid, 16))
    except ValueError:
        return ""
    return KNOWN_PRINTERS.get(key, "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="spock2-probe-usb",
        description=(
            "Listet USB-Geräte/Serials für CUPS-URI und udev-Zuordnung. "
            "Kein Produktivdruckpfad – nur Diagnose."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Ausführliche Hinweise")
    parser.add_argument(
        "--printers-only",
        action="store_true",
        help="Nur bekannte Thermodrucker-Vendor/Product-IDs anzeigen",
    )
    args = parser.parse_args(argv)

    print(f"Plattform: {platform.system()} {platform.release()}")
    print("Hinweis: Produktivdruck läuft ausschließlich über CUPS-Queues.\n")

    devices = collect_devices(verbose=args.verbose)
    if not devices:
        print(
            "Keine USB-Geräte gefunden.\n"
            "  • Linux: pyusb installieren oder /sys lesen (als User in Gruppe lp).\n"
            "  • Windows: pyusb + libusb; Serials ggf. im Geräte-Manager prüfen.",
            file=sys.stderr,
        )
        return 1

    shown = 0
    for dev in devices:
        hint = _hint_known(dev.vendor_id, dev.product_id)
        if args.printers_only and not hint:
            continue
        shown += 1
        label = f"  [{hint}]" if hint else ""
        print(
            f"{dev.vendor_id}:{dev.product_id}  "
            f"bus={dev.bus} addr={dev.address}  "
            f"serial={dev.serial or '(leer)'}  "
            f"product={dev.product or '?'}  "
            f"via={dev.source}{label}"
        )
        if args.verbose and dev.manufacturer:
            print(f"    manufacturer={dev.manufacturer}")

    if shown == 0:
        print("Keine passenden Drucker-IDs (Filter --printers-only).", file=sys.stderr)
        return 1

    print(
        "\nNächste Schritte:\n"
        "  1. Serial in CUPS Device-URI binden (z. B. usb://...serial=...)\n"
        "  2. Queues spock-kitchen / spock-counter / spock-small anlegen\n"
        "  3. spock2-test-print --role kitchen ausführen"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
