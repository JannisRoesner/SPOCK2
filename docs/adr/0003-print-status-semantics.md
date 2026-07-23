# ADR 0003: Print-Statussemantik (submitted ≠ printed)

- **Status:** Accepted
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0)

## Context

Nach `pycups`-Submit meldet CUPS schnell `completed`, insbesondere bei Raw-Queues. Das bedeutet nicht zwingend, dass der Thermodrucker den Bon ausgegeben und geschnitten hat. Papierende, Offline-Gerät oder Treiberpuffer können zu falscher „Erfolg“-Anzeige führen. Operatoren brauchen ehrliche Zustände und Retry-Hinweise statt stiller Annahmen.

## Decision

Statusmaschine der SQLite-`print_jobs`:

| Status | Bedeutung |
| --- | --- |
| `pending` | Enqueued, noch nicht an CUPS übergeben |
| `submitted` | An CUPS übergeben (Job-ID bekannt); **nicht** physisch fertig |
| `printing` | CUPS/IPP meldet aktive Verarbeitung |
| `completed` | Terminaler CUPS-/Timeout-Erfolg nach Policy |
| `failed` | Endgültig fehlgeschlagen nach Max-Retries |
| `cancelled` | Abgebrochen |
| `unknown` | CUPS weg, Job-ID verloren, Restart-Ambiguity |

Übergänge (vereinfacht):

- `pending → submitted → printing → completed`
- `pending|submitted|printing → failed` (Retry zurück nach `pending` bis Max)
- `* → cancelled`
- `submitted|printing → unknown` bei CUPS-Verlust

Zusätzlich:

1. UI/StatusBar unterscheidet „an CUPS“ vs. „vermutlich gedruckt“.
2. Bei Raw-Queues: Timeout + Operator-Hinweis, wenn kein zuverlässiger Terminalstatus.
3. **Druck ≠ Erledigt** (siehe ADR 0012): Complete ändert den Print-Status nicht.

## Consequences

### Positiv

- Vermeidet Fake-Erfolge; bessere Diagnose nach CUPS-Restart.
- Retry-Policy und `unknown` sind modellierbar und testbar.

### Negativ / Risiken

- Operatoren müssen `unknown`/`failed` verstehen (Schulung).
- Striktere Semantik kann „fertig“ später melden als alt-SPOCK.

### Follow-up

- Hardwarematrix: Cutter und Papierende gegen Statusanzeige prüfen.
- Logging: Statusübergänge strukturiert, ohne Secrets.
