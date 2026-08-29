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

## Endlosrolle: Seitengeometrie

CUPS kennt kein Endlospapier — die Raster-Pipeline braucht die Seitenlänge
vorab. SPOCK2 erzeugt deshalb je Job ein PDF, dessen Seite **genau so lang ist
wie der Bon**, und fordert exakt dieses Medium an. Das ist das Gegenstück zum
Windows-Format „72 mm × Receipt“ (Papiertyp *Receipt* = „printed to last line“).

Pro Job mitgeschickte Optionen:

| Option                  | Wert               | Wirkung                          |
|-------------------------|--------------------|----------------------------------|
| `media`                 | `Custom.204x<H>`   | Medium == Seite, kein Skalieren  |
| `nopdfAutoRotate`       | `true`             | pdftopdf dreht nicht             |
| `orientation-requested` | `3`                | Portrait                         |
| `print-scaling`         | `none`             | Kein Fit-to-Page                 |
| `fit-to-page`           | `false`            | dito für ältere cups-filters     |

Maße in **PostScript-Punkten**, weil die PDF-MediaBox ebenfalls in Punkten
steht — so entsteht kein Rundungsversatz. Die Breite ist die *bedruckbare*
Breite, nicht die Rollenbreite: 80-mm-Papier hat 576 Punkte = 204 pt = 72 mm.
Genau das ist auch das Maximum der Star-PPD
(`*ParamCustomPageSize Width: 1 points 72 204`) — mit 80 mm (227 pt) würde CUPS
die Option ablehnen.

Queue prüfen:

```bash
spock2-probe-queue --role kitchen
```

Das liest die PPD der Queue und meldet, ob `VariablePaperSize` gesetzt ist und
ob die realen Bonlängen in die Custom-Grenzen passen. Manuell:

```bash
lpoptions -p spock-kitchen -l | grep -i pagesize
```

Fehlt Custom-PageSize (z. B. bei `-m raw` oder `-m everywhere`), lehnt CUPS die
Optionen ab; SPOCK2 sendet den Job dann ohne Geometrie-Optionen erneut und loggt
`event=cups_options_rejected` — der Bon kommt in diesem Fall wieder
gedreht/gestaucht heraus. Dann die Queue mit der Hersteller-PPD (`starcupsdrv`)
neu anlegen.

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
