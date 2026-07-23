# ADR 0009: Packaging, systemd und Kiosk

- **Status:** Accepted
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0)

## Context

Produktivziel ist Ubuntu 24.04 auf dem Latitude 5285 als Touch-Kiosk, nicht Windows-Desktop. Alt-SPOCK setzte auf PyInstaller multi-OS; für Linux-Ops sind `.deb`, systemd, udev und Logrotation wartbarer. Autostart nach Login und unterdrücktes Display-Blanking sind Event-kritisch.

## Decision

1. **Primärlieferung:** Paket `spock2` als **`.deb`** (wheel → debhelper); RPM optional später.
2. **Dependencies:** CUPS, Treiber/Filter, Qt-Plattformbibliotheken, User in Gruppe `lp`.
3. **udev:** Regeln für Serial/by-path-Symlinks (`deploy/udev/`).
4. **systemd user service:** `After=graphical-session cups.service network-online.target`, `Restart=on-failure`.
5. **Kiosk:** Vollbild-Flag der App + Session-Script (DPMS/`xdg-screensaver` aus), Autostart nach Login.
6. **Logs:** journald + rotierende Dateien unter `/var/log/spock2/` oder `~/.local/state/spock2/`.
7. **Config:** `/etc/spock2/` (bleibt bei Update/Rollback).
8. **Rollback:** apt-Pin / Paket `spock2-prev` bzw. vorherige Version bereithalten; Alt-SPOCK als Event-Fallback.

## Consequences

### Positiv

- Reproduzierbare Installationen und Updates.
- Klare Trennung App vs. Systemdruck vs. Session.
- Ops-freundlich (journalctl, systemctl --user).

### Negativ / Risiken

- Kiosk hängt an Display-Manager/Session-Setup des Geräts.
- User-systemd vs. System-Unit muss dokumentiert werden.
- Windows bleibt Dev-only (siehe `docs/dev-windows.md`).

### Follow-up

- Phase 8: `packaging/deb`, Service-Units, Kiosk-Script.
- Abnahme: Install → Login → Kiosk → Testprint.
