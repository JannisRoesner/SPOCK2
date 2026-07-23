# ADR 0007: TSP100-Treiber- und Renderstrategie

- **Status:** Proposed (pending hardware)
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0) — **Finalisierung nach Hardwaretest**

## Context

Zwei Star TSP100 (80 mm, Cutter) sind Produktivziel für `spock-kitchen` und `spock-counter`. Unter Ubuntu ist die optimale Anbindung unklar: offizieller/community CUPS-Filter (z. B. `rastertotsp100`), Line Mode, oder generische Raw-Queue mit vorgerendertem Raster/Text. Blindes ESC/POS ist für TSP100 riskant. Die alte S3-Driver-URL ist abgelaufen und darf nicht als Abhängigkeit dienen. Hardware (Serials, Cutter) ist ggf. noch nicht vor Ort — Tests dürfen deferred werden; Entwicklung startet mit 5890K/CUPS-PDF.

## Decision (vorläufig)

1. **Kein** Produktiv-PyUSB-Pfad (ADR 0001).
2. Profil `tsp100`: 80 mm, Cutter erwartet, Encoding/Capabilities nach Messung.
3. Kandidaten (zu bewerten auf echte Hardware):
   - **A:** Star/Community-CUPS-Filter + gerendertes Raster/PDF/Image
   - **B:** Raw-Queue + SPOCK2-Renderer liefert gerätegeeignete Bytes (nur wenn A ungeeignet)
4. Entscheidung **A vs. B** erst nach Phase-0/7-Messung; bis dahin bleibt dieses ADR **Proposed**.
5. Vertauschungsschutz über USB-Serial in URI; Fallback udev by-path + Kabel-Labels.
6. Entwicklung/CI ohne TSP100: CUPS-PDF oder POS 5890K als Platzhalter-Queues.

## Consequences

### Positiv

- Explizite Offenheit verhindert Fehlentscheidungen ohne Gerät.
- Parallelentwicklung der App ist nicht blockiert.

### Negativ / Risiken

- Phase 7 kann Treiberwechsel erzwingen (Renderer-Anpassung).
- Cutter-Verhalten ist treiberabhängig.
- Fehlende Serials erzwingen by-path-Ops-Aufwand.

### Follow-up

- [ ] Serials beider TSP100 dokumentieren
- [ ] Testbon + Cutter + Umlaute je Kandidat A/B
- [ ] Status dieses ADR auf **Accepted** setzen und gewählte Option festhalten
- [ ] Deploy-Paket um benötigte Filter/PPD ergänzen
