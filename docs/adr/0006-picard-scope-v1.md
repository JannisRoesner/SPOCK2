# ADR 0006: PICARD-Scope in V1.0

- **Status:** Accepted
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0)

## Context

Alt-SPOCK integrierte PICARD-Zettel (Empfang, Anzeige, Schreiben, Auto-Print). PICARD bietet **kein** Küchen-Druck-API – nur Zettel-Endpoints. Session-IDs sind UUIDs; der Altcode hatte fehlerhafte Pfade (`/api/sitzung/aktiv`) und hartes `picard_session_id: 1`. Für Parität und Event-Betrieb sollen Zettel in V1.0 verfügbar, aber abschaltbar sein.

## Decision

1. PICARD ist in **V1.0 implementiert** als eigenes Modul.
2. Per TOML abschaltbar: `picard.enabled = false` → Null-Client, keine Polls, keine UI-Zettel.
3. Prod-Default analog Altverhalten: `auto_print_new_notes = true` (in Prod-Config), klar getrennt von Order-Complete.
4. Session-Auflösung: `GET /api/aktive-sitzung`, Fallback Liste; Config-Override erlaubt.
5. Filter Kitchen-Targets tolerant/normalisiert (Typ u. a. `anKueche`).
6. Schreib-Dialog mit Zielwahl (`anAlle` / `anModeration` / …) – kein hardcodiertes Ziel.
7. **Nicht** in V1: PICARD als Ersatz für RIKER-Orderdruck, Auth-Login-Flow, Filesystem-Watcher.

## Consequences

### Positiv

- Feature-Parität zum Alt-SPOCK; Modul bleibt optional für reine Küchen-Tablets.
- Korrekte Session-API verhindert stille Leerläufe.

### Negativ / Risiken

- Zusätzliche Fehlerfläche (Netz, Session fehlt).
- Auto-Print Notes braucht eigenes Ledger (`picard_note`).
- UI-Komplexität (Overlay-Karten, Admin-Historie).

### Follow-up

- Phase 2/6: Client, Poll, UI, Auto-Print Notes.
- Abnahmekriterium: Modul aus → nuller Einfluss auf Order-Pfad.
