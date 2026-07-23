# ADR 0004: Dedup- und Ledger-Strategie

- **Status:** Accepted
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0)

## Context

Alt-SPOCK speicherte `printed_order_ids` / `seen_note_ids` nur im Speicher. Nach Neustart wurden offene Bestellungen erneut auto-gedruckt. Für Event-Betrieb ist Doppeldruck inakzeptabel. Gleichzeitig müssen manuelle Nachdrucke weiterhin möglich sein.

## Decision

Zwei persistente Mechanismen in SQLite:

1. **`print_jobs`** mit Unique-Index für Auto-Jobs:

   ```text
   UNIQUE (source_type, source_id, target_role, payload_hash)
   WHERE is_reprint = 0 AND status NOT IN ('cancelled','failed')
   ```

2. **`source_ledger`**: merkt `first_seen` / `last_seen` / `auto_enqueued` je `(source_type, source_id)`.

Regeln:

- Auto-Print: Hash aus kanonischem Payload; bei Restart keine neuen Auto-Jobs für bereits geloggte Quellen.
- Nachdruck: neuer Job mit `is_reprint = 1` (kein Unique-Konflikt).
- Failed/cancelled Auto-Jobs dürfen nach Policy erneut versucht werden (Index erlaubt das für Terminal-Fail).
- Dedup gilt **pro Zielrolle**: eine Bestellung kann mehrere Rollen-Jobs erzeugen (ADR 0005).

## Consequences

### Positiv

- Neustart-sicher gegen Doppel-Auto-Druck.
- Nachdruck bleibt explizit und auditierbar.
- Testbar (Unit: Index + Ledger-AC).

### Negativ / Risiken

- Payload-Änderungen (z. B. Item-Update) erzeugen neuen Hash → ggf. neuen Auto-Job (gewollt dokumentieren).
- Ledger-DB-Pflege und Migrationen nötig.
- Parallelbetrieb Alt+Neu mit beiden Auto-Print aktiv umgeht clientseitiges Dedup (Betriebsregel).

### Follow-up

- AC: „Dedup nach Restart“ in Phase 4/9.
- DB-Ort und Backup in Deploy-Doku.
