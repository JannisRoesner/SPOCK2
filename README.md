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

Config-Suche: `SPOCK2_CONFIG` → `config/spock2.toml` → `%APPDATA%/spock2/spock2.toml` (Windows)
bzw. `/etc/spock2/` und `~/.config/spock2/` (Linux).

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
| Linux | `auto` → CUPS, oder `cups` | UTF-8-Text |
| Windows | `auto` → WinSpool, oder `winspool` | ESC/POS RAW |
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
| `[tls]` | `ssl_verify` |
| `[polling]` / `[backoff]` | Poll-Intervall, Exponential Backoff |
| `[printers.*]` | Rolle → `queue` + Profil |
| `[routing]` | `station_role`, Kategorie→Rollen |
| `[print]` | Auto-Print, `transport`, Retries |
| `[ui]` | Vollbild / Kiosk / Theme |
| `[logging]` / `[db]` | Log-Level, DB-Pfad |
| `[diagnostics]` | Diagnose-Flags |

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
