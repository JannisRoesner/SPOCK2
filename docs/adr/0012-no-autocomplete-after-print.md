# ADR 0012: Kein Auto-Complete nach Druck (Default)

- **Status:** Accepted
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0)

## Context

Druck und „Bestellung erledigt“ sind fachlich getrennte Aktionen. Auto-Complete nach erfolgreichem Druck würde Bestellungen aus RIKER entfernen, bevor die Küche sie ggf. nacharbeiten oder erneut drucken kann. RIKER-Complete ist soft-idempotent ohne strengen Existenz-Check — Fehlerhafte Automatik ist schwer nachzuvollziehen. Operatoren brauchen eine bewusste Touch-Aktion „Erledigt“.

## Decision

1. **Default:** Druck (Auto oder manuell) markiert die Bestellung **nicht** als erledigt.
2. Erledigt nur über expliziten UI-Button → asynchrones `POST /api/orders/:id/complete`.
3. Auto-Print und Complete sind getrennte Config-Schalter; Complete-after-Print ist in V1 **nicht** der Default und sollte, falls jemals angeboten, opt-in und gut sichtbar sein.
4. Print-Status in der Queue bleibt von Complete unberührt (ADR 0003).
5. Doppelklick-Schutz / In-Flight-Set clientseitig.

## Consequences

### Positiv

- Weniger versehentliches Entfernen aus der offenen Liste.
- Nachdruck und Korrekturen bleiben möglich.
- Entspricht Küchen-Workflow (Bon ≠ fertig).

### Negativ / Risiken

- Operator muss „Erledigt“ aktiv tippen (Schulung).
- Offene Liste kann länger wachsen, wenn Complete vergessen wird.

### Follow-up

- Schulungsblatt: Unterschied Auto-Print vs. Erledigt.
- Optional Bestätigungsdialog für Erledigt (abschaltbar).
