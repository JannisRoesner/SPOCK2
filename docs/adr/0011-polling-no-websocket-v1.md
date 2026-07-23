# ADR 0011: Polling in V1 — kein WebSocket/SSE-Zwang

- **Status:** Accepted
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0)

## Context

RIKER exponiert aktuell REST ohne WebSocket/SSE. Alt-SPOCK pollte alle ~3 s. Für V1 wäre die Einführung eines Push-Kanals eine Server- und Client-Änderung ohne bestehenden Vertrag. Polling reicht für Küchen-Latenz im Sekundenbereich, wenn Single-Flight und Backoff korrekt sind.

## Decision

1. V1 nutzt ausschließlich **HTTP-Polling** (RIKER Orders, optional PICARD Zettel).
2. Intervall konfigurierbar (typisch 2–3 s); **Single-Flight** (kein paralleles Poll).
3. Bei Fehlern: Exponential Backoff (z. B. 3→6→12→30 s Cap), Reset bei Erfolg.
4. Kein Filesystem-Watcher auf RIKER-`prints/`.
5. WebSocket/SSE bleiben **bewusst außerhalb von V1**; erneutes ADR bei Server-Support.

## Consequences

### Positiv

- Passt zum bestehenden RIKER-Vertrag.
- Einfacher zu testen (Mocks) und zu betreiben (Firewall/Proxy).
- Backoff schont Server bei Outages.

### Negativ / Risiken

- Leichte Verzögerung vs. Push (akzeptabel für Küche).
- Falsches Intervall kann Last erzeugen — Config und Caps beachten.
- Spätere Push-Migration erfordert Worker-Umbau.

### Follow-up

- Phase 2: `PollWorker` + Backoff-Tests.
- Keine UI-Annahme „Echtzeit &lt; 1 s“.
