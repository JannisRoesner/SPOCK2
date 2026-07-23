# ADR 0001: CUPS als Produktiv-Druckpfad statt Direct-USB

- **Status:** Accepted
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0)

## Context

Das alte SPOCK nutzte optional einen USB-Direktpfad (`prefer_usb_direct` / PyUSB) als Primärweg für Star TSP100. Mit zwei TSP100 und einem POS 5890K führt Direct-USB zu instabiler Gerätezuordnung (`/dev/usb/lp0` wechselt), fehlendem Job-Status und schwierigem Replug-/Hub-Verhalten. Für den Kiosk-Betrieb auf dem Dell Latitude 5285 unter Ubuntu 24.04 wird ein wartbarer, rollenbasierter Mehrdrucker-Betrieb benötigt.

## Decision

1. **CUPS ist der einzige Produktiv-Druckpfad** in SPOCK2.
2. Die App kennt nur logische Queue-Namen (`spock-kitchen`, `spock-counter`, `spock-small`), niemals volatile Device-Nodes.
3. Transport erfolgt über **pycups** (`printFile` / vergleichbar); `lp`/`lpstat` dienen nur Diagnose/Fallback.
4. **PyUSB** darf ausschließlich in Diagnose-Tools (`probe_usb`) vorkommen, nicht im PrintWorker.
5. Stabile Bindung: USB-Serial in der CUPS Device-URI, Fallback udev by-path-Symlinks.

## Consequences

### Positiv

- Einheitliches Job- und Queue-Management, bessere Replug-/Restart-Robustheit.
- Rollenrouting unabhängig vom physischen Port.
- Paketierbare Treiber/PPDs und bekannte Linux-Ops-Werkzeuge.

### Negativ / Risiken

- Abhängigkeit von `cupsd` und korrekter Queue-Konfiguration.
- CUPS-`completed` bedeutet nicht immer „Bon physisch geschnitten“ (siehe ADR 0003).
- TSP100-Treiberwahl unter Ubuntu bleibt Hardware-abhängig (ADR 0007).

### Follow-up

- Phase 0/7: Serials, udev, Replug-Matrix dokumentieren.
- Kein Windows-GDI-Primärpfad in V1.
