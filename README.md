# SPOCK2

Modularer **PySide6**-Kiosk-Client für Linux (Ubuntu 24.04) als Nachfolger des Tkinter-SPOCK.
Holt offene Bestellungen von **RIKER**, optional Zettel von **PICARD**, und druckt über **CUPS**-Rollenqueues
(`spock-kitchen`, `spock-counter`, `spock-small`) mit persistenter SQLite-Druckqueue.

## Voraussetzungen

- Python **3.12+**
- Linux für produktiven Druck (`pycups` / CUPS); Entwicklung unter Windows ist möglich
- Laufendes RIKER (und optional PICARD)

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
# Auf Linux zusätzlich CUPS-Bindung:
pip install -e ".[cups,dev]"
```

Beispiel-Konfiguration kopieren und anpassen:

```bash
cp config/spock2.example.toml config/spock2.toml
# oder: export SPOCK2_CONFIG=/etc/spock2/spock2.toml
```

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
```

## Konfiguration

TOML-Datei (Standardsuche bzw. `SPOCK2_CONFIG`):

| Bereich | Inhalt |
|--------|--------|
| `[riker]` / `[picard]` | Basis-URLs, Timeouts, PICARD `enabled` |
| `[tls]` | `ssl_verify` |
| `[polling]` / `[backoff]` | Poll-Intervall, Exponential Backoff |
| `[printers.*]` | Rollen → CUPS-Queue + Profil |
| `[routing]` | `station_role`, Kategorie→Rollen |
| `[print]` | Auto-Print, Kopien, Max-Retries |
| `[ui]` | Vollbild / Kiosk |
| `[logging]` / `[db]` | Log-Level, DB-Pfad |
| `[diagnostics]` | Diagnose-Flags |

## Architektur (Kurz)

```
UI (PySide6)  →  Services  →  Workers (Poll / Print / CUPS-Status)
                     ↓
              RikerClient / PicardClient (httpx)
                     ↓
              SQLite (print_jobs + source_ledger) → CupsTransport
```

- UI-Thread ohne HTTP/Druck
- Dedup über Unique-Index + Source-Ledger (kein Doppeldruck nach Restart)
- Druck ≠ Erledigt (kein Auto-Complete nach Druck als Default)

## Entwicklung

```bash
ruff check src tests
pytest
```

Unter **Windows**: PySide6-Installation kann an Long-Path-Limits scheitern
(siehe Microsoft-Doku „Enable Win32 long paths“). Core-Tests laufen mit
`PYTHONPATH=src`. Druck geht lokal über `FileTransport`; produktiver CUPS-Pfad
unter Linux (Latitude oder `vagrant up` – siehe [docs/dev-windows.md](docs/dev-windows.md)).

## Dokumentation

| Dokument | Inhalt |
|----------|--------|
| [docs/hardware-checklist.md](docs/hardware-checklist.md) | Hardware-Vorabtests |
| [docs/hardware-matrix.md](docs/hardware-matrix.md) | Phase-7 Pass/Fail-Matrix |
| [docs/adr/](docs/adr/) | Architecture Decision Records |
| [docs/migration.md](docs/migration.md) | Migration Alt-SPOCK → SPOCK2 |
| [docs/acceptance.md](docs/acceptance.md) | Abnahme / Cutover |
| [docs/schulung.md](docs/schulung.md) | Bediener-Kurzblatt |
| [deploy/](deploy/) | CUPS, udev, systemd, Kiosk |
| [packaging/](packaging/) | `.deb` / RPM |

## Lizenz

AGPL-3.0-or-later – siehe [LICENSE](LICENSE).
