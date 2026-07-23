# ADR 0002: PySide6 mit QThread-Workern

- **Status:** Accepted
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0)

## Context

Im alten SPOCK liefen HTTP-Polling und Druck synchron im Tkinter-UI-Thread (`root.after`). Das führte zu UI-Freezes bei Netzlatenz und Druck. SPOCK2 soll Touch-Kiosk-tauglich sein: Statusleiste und Order-Cards müssen auch bei RIKER-Timeouts und CUPS-Last bedienbar bleiben.

Alternativen: asyncio-Eventloop neben Qt, Multiprocessing, separater Print-Daemon. Für V1 erhöhen diese Optionen die Komplexität ohne klaren Gewinn gegenüber Qt-nativen Workern.

## Decision

1. **PySide6** als UI-Toolkit (kein Tk-Port, kein Electron/Web für V1).
2. **Qt-Hauptthread** nur für UI.
3. Dedizierte **QThread/QObject-Worker**:
   - `PollWorker` – RIKER/PICARD-Polling (Single-Flight)
   - `PrintWorker` – Queue-Drain, Render, CUPS-Submit
   - `CupsStatusWorker` – Job-State-Polling
4. Kommunikation ausschließlich über **Signale/Slots**; Shared State über Services und SQLite-Transaktionen.
5. Ein Prozess `spock2` in V1; kein Split Headless-Print-Daemon.

## Consequences

### Positiv

- UI bleibt responsiv; klare Fehlerisolation.
- Passt zu PySide6-Lifecycle und Kiosk-Vollbild.
- Testbar: Worker-Logik von Widgets entkoppelbar.

### Negativ / Risiken

- Thread-Disziplin nötig (kein UI-Zugriff aus Workern).
- Signale müssen typisiert und dokumentiert sein.
- Späterer Split in Daemon erfordert API-Schnittstelle (bewusst nicht V1).

### Follow-up

- Inflight-Guards für Poll und Complete.
- Keine synchronen httpx/pycups-Aufrufe im UI-Thread (CI/Review-Regel).
