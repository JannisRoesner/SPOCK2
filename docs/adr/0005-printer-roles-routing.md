# ADR 0005: Printer-Rollen und Kategorie-Routing

- **Status:** Accepted
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0)

## Context

Alt-SPOCK kannte keine Druckerrollen und keine Multi-Queue-Logik. In der Praxis sollen Küche, Theke und Kleinbon (58 mm) unterschiedliche Geräte und Layouts nutzen. Manche Stationen bedienen nur eine Rolle; andere Geräte sollen hybrid nach Kategorie filtern. Die Architektur muss beides per Config unterstützen.

## Decision

1. Logische Rollen: **`kitchen` | `counter` | `small`**, gemappt auf CUPS-Queues.
2. **Hybrid-Routing:**
   - `station_role` in der TOML (Station druckt primär diese Rolle), **und**
   - optionale Regeln `category → role(s)`.
3. Eine Bestellung kann **mehrere PrintJobs** erzeugen (eine pro Zielrolle nach Regeln).
4. Die App speichert keine Vendor-IDs oder `/dev/*` in der Business-Logik – nur Queue-Namen und Profile.
5. Bonlayout bleibt kategoriegruppiert (Intent wie Alt-SPOCK); Routing ist davon getrennt.

Beispiel-Config-Idee (illustrativ):

```toml
station_role = "kitchen"
[[routing.rules]]
categories = ["Getränke"]
roles = ["counter"]
```

## Consequences

### Positiv

- Skaliert von Ein-Tablet-Küche bis Multi-Station.
- Testbar ohne Hardware (Fake-Queues).
- Klare Trennung Rendering-Profil vs. Zielrolle.

### Negativ / Risiken

- Falsche Kategorie-Namen in RIKER brechen Regeln (Annahme: Namen stabil / Config pflegen).
- Mehr Jobs pro Order erhöhen CUPS-/Papierverbrauch – Regeln bewusst halten.
- Operator-Schulung: welcher Bon wo landet.

### Follow-up

- Example-TOML mit Rollen/Queues in Phase 1.
- Diagnose-CLI: Testprint je Rolle.
