# SPOCK2

Modularer **PySide6**-Kiosk-Client für **Linux** (CUPS) und **Windows** (WinSpool).
Holt offene Bestellungen von **RIKER**, optional Zettel von **PICARD**, und druckt über
Rollenqueues (`kitchen` / `counter` / `small`) mit persistenter SQLite-Druckqueue.

## Voraussetzungen

- Python **3.12+**
- Linux: CUPS + `pycups` für Produktivdruck
- Windows: installierte Thermodrucker + `pywin32` für Produktivdruck
- Laufendes RIKER (und optional PICARD)

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
# Linux Produktivdruck:
pip install -e ".[cups,dev]"
# Windows Produktivdruck:
pip install -e ".[winspool,dev]"
```

Beispiel-Konfiguration:

```bash
cp config/spock2.example.toml config/spock2.toml
# oder: set SPOCK2_CONFIG=... / export SPOCK2_CONFIG=...
```

Config-Suche in dieser Reihenfolge:

1. `SPOCK2_CONFIG` (zeigt die Variable auf eine fehlende Datei, wird nur gewarnt
   und weitergesucht – der Start bricht nicht ab)
2. `config/spock2.toml` (Repo-/Dev-Layout)
3. `~/.config/spock2/spock2.toml` bzw. `%APPDATA%/spock2/spock2.toml`
4. `/etc/spock2/spock2.toml`

Die Benutzer-Config gewinnt bewusst gegen `/etc`, damit Start aus Shell, Startmenü
und systemd dieselbe Datei benutzen. Wird gar keine Datei gefunden, startet SPOCK2
mit Defaults und schreibt Änderungen aus dem Einstellungsdialog in die Benutzer-Config.

## Start

```bash
spock2
# oder:
python -m spock2
```

Diagnose:

```bash
spock2-probe-usb
spock2-test-print --role kitchen
spock2-test-print --file --role kitchen   # nur Datei-Ausgabe
```

## Druck

| OS | Transport (`print.transport`) | Payload |
|----|-------------------------------|---------|
| Linux | `auto` → CUPS, oder `cups` | PDF im Alt-SPOCK-Look (große Tischnummer, keine umgebrochenen `===`) |
| Windows | `auto` → WinSpool, oder `winspool` | TSP100: GDI (Star-Treiber, große Tischnummer); 58 mm: ESC/POS RAW |
| Dev | `file` | Dateien unter State-Dir / `SPOCK2_PRINT_OUT` |

In `[printers.*]` ist `queue` der CUPS-Queue-Name bzw. der exakte Windows-Druckername
(Alias `cups_queue` bleibt gültig).

## Windows-Hinweise

- PySide6 kann an **Long-Path**-Limits scheitern → „Enable Win32 long paths“ aktivieren.
- State/DB/Logs: `%LOCALAPPDATA%/spock2/`.
- `.exe` bauen:

```powershell
pip install pyinstaller pywin32
pyinstaller packaging/windows/spock2.spec
```

Ausgabe typischerweise unter `dist/spock2/`.

## Konfiguration

| Bereich | Inhalt |
|--------|--------|
| `[riker]` / `[picard]` | Basis-URLs, Timeouts, PICARD `enabled` |
| `[tls]` | `ssl_verify`, `ca_bundle` (siehe unten) |
| `[polling]` / `[backoff]` | Poll-Intervall, Exponential Backoff |
| `[printers.*]` | Rolle → `queue` + Profil |
| `[routing]` | `station_role`, Kategorie→Rollen |
| `[print]` | Auto-Print, `transport`, Retries |
| `[ui]` | Vollbild / Kiosk / Theme |
| `[logging]` / `[db]` | Log-Level, DB-Pfad |
| `[diagnostics]` | Diagnose-Flags |

### HTTPS mit eigenem Zertifikat

Meldet die Statusleiste `RIKER: Zertifikatsfehler` (Log: `CERTIFICATE_VERIFY_FAILED`),
kennt der Client die ausstellende CA nicht. Zwei Wege, beide unter
**Einstellungen → APIs → TLS / Zertifikate** einstellbar:

- **Empfohlen:** CA-Bundle hinterlegen (`tls.ca_bundle`, PEM-Datei der eigenen CA).
- **Notlösung:** `tls.ssl_verify = false` – die Verbindung bleibt verschlüsselt,
  ist aber nicht gegen Fälschung geschützt.

„Verbindung testen“ im selben Reiter prüft RIKER und PICARD mit den aktuell im
Dialog eingestellten Werten, bevor gespeichert wird.

## Fehlersuche

- **Start aus Startmenü/Icon tut nichts:** SPOCK2 zeigt Startfehler seit 0.1.3 als
  Dialog. Zusätzlich landen Fehler im Log (`~/.local/state/spock2/spock2.log`,
  Windows `%LOCALAPPDATA%/spock2/`); der Kiosk-Starter schreibt stderr nach
  `~/.local/state/spock2/session.log`.
- **Drucke kommen nicht:** Die Statusleiste zeigt `Druckfehler: n`, das Log
  `event=print_failed … queue=… err=…`. Häufigste Ursache ist ein Queue-Name, den
  das System nicht kennt – der Drucker-Reiter markiert das rot.

## Architektur (Kurz)

```
UI (PySide6)  →  Services  →  Workers (Poll / Print / Status)
                     ↓
              RikerClient / PicardClient (httpx)
                     ↓
              SQLite → CupsTransport | WinSpoolTransport | FileTransport
```

- UI-Thread ohne HTTP/Druck
- Dedup über Unique-Index + Source-Ledger
- Druck ≠ Erledigt (kein Auto-Complete nach Druck als Default)

## Entwicklung

```bash
ruff check src tests
pytest
```

## Dokumentation

| Dokument | Inhalt |
|----------|--------|
| [deploy/](deploy/) | CUPS, udev, systemd, Kiosk (Linux) |
| [packaging/](packaging/) | `.deb` / RPM / Windows `.exe` |

## Lizenz

AGPL-3.0-or-later – siehe [LICENSE](LICENSE).
