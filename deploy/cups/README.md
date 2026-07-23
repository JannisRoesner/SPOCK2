# CUPS-Queues für SPOCK2

SPOCK2 kennt nur logische Queue-Namen:

| Rolle    | CUPS-Queue       | Typisches Gerät   |
|----------|------------------|-------------------|
| kitchen  | `spock-kitchen`  | Star TSP100 80 mm |
| counter  | `spock-counter`  | Star TSP100 80 mm |
| small    | `spock-small`    | POS 5890K 58 mm   |

Die App speichert keine `/dev/*`-Pfade — nur Queue-Namen in der TOML (`queue`, Alias `cups_queue`).

## Voraussetzungen

```bash
sudo apt update
sudo apt install -y cups cups-client cups-bsd
# Dev / ohne Hardware:
sudo apt install -y printer-driver-cups-pdf   # Ubuntu: oft „cups-pdf“ / cups-pdf-Paket
```

Benutzer der Kiosk-Session in die Gruppe `lp` (und ggf. `lpadmin` für Setup):

```bash
sudo usermod -aG lp,lpadmin "$USER"
# danach neu einloggen
```

## CUPS-PDF zum Testen (ohne Thermodrucker)

Drei Queues, alle auf PDF — ideal für Windows-Devs in der Ubuntu-VM / Vagrant:

```bash
sudo lpadmin -p spock-kitchen -E -v cups-pdf:/ -m everywhere
sudo lpadmin -p spock-counter -E -v cups-pdf:/ -m everywhere
sudo lpadmin -p spock-small   -E -v cups-pdf:/ -m everywhere

sudo cupsenable spock-kitchen spock-counter spock-small
sudo cupsaccept spock-kitchen spock-counter spock-small
```

PDF-Ausgabe typischerweise unter `~/PDF/` (oder `/var/spool/cups-pdf/$USER/`).

Testseite:

```bash
echo "SPOCK kitchen test" | lp -d spock-kitchen
lpstat -p -d
```

## Produktiv: Device-URI mit USB-Serial

Serial auslesen:

```bash
lsusb -v 2>/dev/null | grep -A2 -i serial
# oder
udevadm info -a -n /dev/usb/lp0 | grep ATTRS{serial}
spock2-probe-usb
```

Beispiel Raw-Queue mit Serial in der URI (Treiber/PPD je Hardware anpassen):

```bash
# Platzhalter SERIAL_TSP100_KITCHEN ersetzen
sudo lpadmin -p spock-kitchen -E \
  -v "usb://Star/TSP100?serial=SERIAL_TSP100_KITCHEN" \
  -m raw
  # oder: -P /usr/share/ppd/.../tsp100.ppd

sudo lpadmin -p spock-counter -E \
  -v "usb://Star/TSP100?serial=SERIAL_TSP100_COUNTER" \
  -m raw

sudo lpadmin -p spock-small -E \
  -v "usb://POS/5890K?serial=SERIAL_POS5890K_SMALL" \
  -m raw

sudo cupsenable spock-kitchen spock-counter spock-small
sudo cupsaccept spock-kitchen spock-counter spock-small
```

`lpinfo -v` listet erkannte Device-URIs inkl. Serial — diese Strings bevorzugen.

### Fallback: udev-Symlink

Wenn Serial fehlt: `deploy/udev/99-spock-printers.rules` installieren und URI z. B.:

```bash
sudo lpadmin -p spock-kitchen -E -v serial:/dev/spock-kitchen -m raw
# oder file:/dev/spock-kitchen — je nach Treiber/Backend
```

Kabel und Ports beschriften (Küche / Theke / Klein).

## Konfiguration prüfen

```bash
lpstat -v          # Device-URI je Queue
lpstat -p          # Status enabled/accepting
cupsenable spock-kitchen   # falls paused
cupsaccept spock-kitchen
```

Beispiel-Snippet: [`spock-queues.conf.example`](spock-queues.conf.example) (Dokumentation / Copy-Paste, nicht automatisch von cupsd geladen).

## SPOCK2-Config

In `/etc/spock2/spock2.toml` (oder `SPOCK2_CONFIG`):

```toml
[printers.kitchen]
queue = "spock-kitchen"
# …
```

Siehe `config/spock2.example.toml`.
