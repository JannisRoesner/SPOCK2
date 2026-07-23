# ADR 0008: POS 5890K Capability-Profil

- **Status:** Accepted
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0)

## Context

Der POS 5890K (58 mm, ca. 384 dots) dient als Kleinbon-Drucker (`spock-small`) und als früher Hardware-Anker, während TSP100-Tests aufgeschoben sein können. ESC/POS-Qualität und Cutter-Verhalten sind geräteabhängig und oft eingeschränkt. Ein konservatives Profil verhindert Layout-Brüche und unlesbare QR-Codes.

## Decision

1. Eigenes Profil `pos5890k` mit Capabilities:
   - Papierbreite **58 mm** / ~**384 dots**
   - Cutter: **meist nein** / nicht voraussetzen
   - Text: konservatives ESC/POS **oder** Bitmap-Text, je nach Messung
   - **QR als Bitmap**, nicht als unzuverlässige Native-QR-Sequenz
2. Renderer liest Capabilities aus dem Profil; kein Hardcode von Magic Numbers in UI.
3. Queue `spock-small` ist der einzige App-Bezugspunkt.
4. Frühzeitige Hardware-Checks (Minimalbon, Umlaute, €, Wrap) sind Teil der Phase-0-Checklist.

## Consequences

### Positiv

- Vorhersagbare Bons auf schmalem Papier.
- Ermöglicht Entwicklung/Abnahme ohne TSP100.
- Klare Trennung zu `tsp100`-Layout (80 mm).

### Negativ / Risiken

- Bitmap-Pfade sind CPU-/Tempfile-lastiger.
- Ohne Cutter stapeln sich Bons — Operator-Hinweis in Schulung.
- Schlechte ESC/POS-Implementierung erzwingt stärkeren Rasterpfad.

### Follow-up

- Phase 5: `profiles/pos5890k.py` + Unit-Tests Wrap/Umlaute.
- Ergebnisse in hardware-checklist.md eintragen.
