# Entwickeln unter Windows (SPOCK2)

**Stand:** 2026-07-23  
**Wichtig:** Windows ist **kein** produktives Ziel für V1. Abnahmerelevanter Druckpfad ist **Linux** (Ubuntu 24.04, Latitude 5285, CUPS). Unter Windows können UI, API-Clients, Queue-Logik und Tests entwickelt werden; echter Thermodruck gehört auf Linux/VM.

---

## 1. Empfohlene Dev-Setups

| Setup | Geeignet für | Druck |
| --- | --- | --- |
| **Windows Host** + Python 3.12+ | UI (PySide6), Domain, SQLite, httpx-Mocks | `FileTransport` / Fake |
| **Ubuntu 24.04 VM** (Hyper-V/VMware/VirtualBox) | CUPS, pycups, udev-Nähe, `.deb` | CUPS-PDF + ggf. USB-Passthrough |
| **WSL2** | Teile der Linux-Tooling; GUI/CUPS eingeschränkt | nur bedingt — VM bevorzugen für CUPS |

Empfehlung: Alltag auf Windows, Druck-/Deploy-Themen in einer Ubuntu-VM.

---

## 2. FileTransport (Dev ohne CUPS)

Statt `CupsTransport` in der Dev-Config einen Datei-Transport aktivieren (Name/Flag laut späterer TOML, z. B. `transport = "file"`):

- Renderer schreibt Bon-Bytes oder Text nach `%LOCALAPPDATA%/spock2/out/` bzw. konfigurierbares Verzeichnis.
- Job-Status kann sofort `completed` oder über eine kleine Fake-State-Maschine simuliert werden.
- Ermöglicht Tests von Orchestrator, Dedup, Nachdruck und UI-Status **ohne** Drucker.

Regel: FileTransport **niemals** in Prod-Config auf dem Latitude.

---

## 3. Ubuntu-VM mit CUPS-PDF

1. Ubuntu 24.04 VM, Gast-Additions/Tools für Clipboard/Ordnerfreigabe.  
2. Pakete grob: `cups`, `cups-pdf` (oder aktuelle PDF-Queue), `python3`, Build-Deps für PySide6/pycups.  
3. Drei Queues anlegen — auch wenn alle auf PDF zeigen:

   ```bash
   # Beispielskizze — genaue PPD/URI je Distro anpassen
   lpadmin -p spock-kitchen -E -v cups-pdf:/ -m everywhere
   lpadmin -p spock-counter -E -v cups-pdf:/ -m everywhere
   lpadmin -p spock-small   -E -v cups-pdf:/ -m everywhere
   cupsenable spock-kitchen spock-counter spock-small
   cupsaccept spock-kitchen spock-counter spock-small
   ```

4. PDF-Ausgabeordner prüfen (`~/PDF` o. ä.), Dateinamen/Jobs den Rollen zuordnen.  
5. SPOCK2 gegen diese Queue-Namen betreiben; `pycups`-Submit und Status-Worker üben.  
6. Optional: USB-Passthrough für POS 5890K / TSP100, sobald Hardware da ist.

---

## 4. Typischer Windows-Workflow

```text
Windows: pytest, Ruff, UI-Prototyp, FileTransport
    ↕ git
Ubuntu-VM: CupsTransport, CUPS-PDF, später echtes Gerät
    → Phase 7/8 auf Latitude
```

1. Repo klonen, venv, `pip install -e ".[dev]"` (sobald `pyproject.toml` existiert).  
2. Config aus Example: RIKER/PICARD auf localhost/Staging; `ssl_verify` bewusst setzen.  
3. UI starten: `python -m spock2` — Poll gegen Mock oder Staging.  
4. Druckpfad: FileTransport lokal; periodisch VM-Lauf mit CUPS-PDF.  
5. Keine Annahme, dass Win32-Druck oder Notepad-Workarounds aus Alt-SPOCK zurückkehren.

---

## 5. Was unter Windows bewusst fehlt / abweicht

| Thema | Windows-Dev | Prod-Linux |
| --- | --- | --- |
| CUPS / pycups | oft nicht | Pflicht |
| udev / Serial-Symlinks | n/a | Pflicht |
| systemd user service / Kiosk | n/a | Phase 8 |
| Touch/DPI Latitude | nur näherungsweise | Gerätetest |
| TSP100-Cutter | deferred/VM+USB | Phase 7 |

---

## 6. Tests

- **Unit** auf Windows: Modelle, Dedup, Renderer-Text, Backoff, Config.  
- **Integration** mit httpx-Mock und SQLite temp DB.  
- **CUPS-Integration** in VM oder CI-Linux-Runner.  
- Hardware-Checklist/Matrix nur auf echtem Stack ausfüllen.

---

## 7. Referenzen

- [hardware-checklist.md](hardware-checklist.md) — TSP100 deferred, 5890K/PDF zuerst  
- [adr/0001-cups-vs-usb.md](adr/0001-cups-vs-usb.md) — CUPS Prod-only  
- [adr/0009-packaging-systemd-kiosk.md](adr/0009-packaging-systemd-kiosk.md) — Lieferform  
- [migration.md](migration.md) — Cutover vom Alt-Client
