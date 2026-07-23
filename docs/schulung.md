# SPOCK2 — Kurzanleitung Bedienung (1 Seite)

**Gerät:** Küchen-/Theken-Tablet (Dell Latitude 5285)  
**Bei Problemen:** Technik / Schichtleitung — Rollback: Alt-SPOCK bereithalten

---

## Start

1. Tablet einschalten und anmelden (falls gefordert).  
2. SPOCK2 startet im Vollbild (Kiosk).  
3. Unten in der **Statusleiste** prüfen: RIKER (und ggf. PICARD) grün/verbunden, Drucker/Queues ok.

| Farbe / Zustand (typisch) | Bedeutung |
| --- | --- |
| Verbunden / ok | Normalbetrieb |
| Verbinden… | Kurz warten |
| Offline / Fehler | Netz oder Dienst prüfen — letzte Bestellliste bleibt sichtbar |
| Drucker/Queue Warnung | Papier, Kabel, CUPS — Technik rufen |

---

## Bestellungen

- Neue Bestellungen erscheinen als **große Karten** (Tisch/Gast, Artikel, Mengen, Notizen, Wartezeit).  
- **Automatischer Druck** (wenn eingeschaltet): neuer Bon kommt von allein auf dem richtigen Drucker.  
- **Nachdruck:** Button auf der Karte — erzeugt einen weiteren Bon (absichtlich).  
- **Erledigt:** erst tippen, wenn die Bestellung wirklich fertig ist. Die Karte verschwindet nach Erfolg aus der offenen Liste.

### Wichtig

**Druck ≠ Erledigt.** Ein gedruckter Bon bedeutet nicht, dass die Bestellung in RIKER geschlossen ist. Erst **Erledigt** schließen.

---

## Zettel (PICARD, falls aktiv)

- Neue Küchen-Zettel können als Hinweis/Karte erscheinen und ggf. mitgedruckt werden.  
- Zettel schließen, wenn erledigt; Schreiben nur nach Absprache (Ziel wählen).

---

## Drucker kurz

| Rolle | Typisch | Papier |
| --- | --- | --- |
| Küche | Star TSP100 | 80 mm |
| Theke | Star TSP100 | 80 mm |
| Klein | POS 5890K | 58 mm |

- Papierende / Stau / kein Bon trotz Anzeige → **nicht** wild neu stecken ohne Label; Technik.  
- Kabel sind beschriftet (Kitchen/Counter) — nicht vertauschen.

---

## Notfall

1. Ruhe bewahren — Bestellungen ggf. auf dem Bildschirm ablesen.  
2. Technik informieren.  
3. Auf Anweisung: SPOCK2 beenden / Auto-Print aus, **Alt-SPOCK** starten (nur ein System darf Auto-Print haben).

---

*SPOCK2 V1 — Schulungsblatt. Details: `docs/acceptance.md`, Technik: ADRs unter `docs/adr/`.*
