# Hardware-Testmatrix (Phase 7)

**Zweck:** Abschließende Pass/Fail-Matrix für Dell Latitude 5285 mit allen Produktivdruckern und Robustheitsszenarien.  
**Voraussetzung:** Phase-0-Baseline ([hardware-checklist.md](hardware-checklist.md)), CUPS-Queues, udev, Profile `tsp100` / `pos5890k`.  
**Datum:** _______________ **Tester:** _______________ **SPOCK2-Version:** _______________

Legende: **P** = Pass · **F** = Fail · **N/A** = nicht anwendbar · **DEF** = aufgeschoben (nur mit Begründung)

---

## Geräteübersicht

| Rolle | Queue | Profil | Gerät | Serial / by-path | Bereit |
| --- | --- | --- | --- | --- | --- |
| kitchen | `spock-kitchen` | tsp100 | Star TSP100 #1 | | ☐ |
| counter | `spock-counter` | tsp100 | Star TSP100 #2 | | ☐ |
| small | `spock-small` | pos5890k | POS 5890K | | ☐ |
| (Dev) | beliebige | — | CUPS-PDF | n/a | ☐ |

---

## 1. Basisdruck je Gerät

| # | Szenario | Kitchen | Counter | Small | Notiz |
| --- | --- | --- | --- | --- | --- |
| B1 | Diagnose-Testseite (`lp` / CLI) | | | | |
| B2 | SPOCK2 Manual-Testprint | | | | |
| B3 | Auto-Print RIKER-Order | | | | |
| B4 | Manueller Nachdruck (`is_reprint=1`) | | | | |
| B5 | PICARD-Zettel-Druck (falls enabled) | | | | N/A wenn Modul aus |

---

## 2. Zeichensatz & Layout

| # | Szenario | Kitchen | Counter | Small | Notiz |
| --- | --- | --- | --- | --- | --- |
| L1 | Umlaute (äöüÄÖÜß) | | | | |
| L2 | Euro-Zeichen € | | | | |
| L3 | Lange Artikelnamen (Wrap) | | | | |
| L4 | Lange Notizen / Sonderzeichen | | | | |
| L5 | Kategorie-Gruppierung wie Alt-SPOCK-Intent | | | | |
| L6 | Leere Items / Edge-Cases abgefangen | | | | |
| L7 | QR als Bitmap (falls Profil aktiv) | N/A? | N/A? | | |

---

## 3. Cutter / Papier

| # | Szenario | Kitchen | Counter | Small | Notiz |
| --- | --- | --- | --- | --- | --- |
| C1 | Vollschnitt / Partial-Cut wie Profil | | | | 5890K meist ohne Cutter |
| C2 | Mehrere Bons hintereinander, klar getrennt | | | | |
| C3 | Papierende / Cover-offen → sichtbarer Fehler | | | | |
| C4 | Kein Phantom-„completed“ ohne physischen Bon | | | | Statusmodell ADR 0003 |

---

## 4. Gerätezuordnung & Replug

| # | Szenario | Kitchen | Counter | Small | Notiz |
| --- | --- | --- | --- | --- | --- |
| R1 | Replug idle → gleicher Symlink/Queue | | | | |
| R2 | Replug während pending Job | | | | |
| R3 | Job nach Replug am **richtigen** Gerät | | | | |
| R4 | Vertauschungsschutz: Kabel tauschen | | | | Kitchen≠Counter |
| R5 | USB-Hub aktiv: Stabilität unter Last | | | | |
| R6 | Cold-Boot: Queues enabled, App startet | | | | |

---

## 5. CUPS-Robustheit

| # | Szenario | Erwartung | Ergebnis | Pass/Fail |
| --- | --- | --- | --- | --- |
| Q1 | `systemctl restart cups` idle | Health recovered | | |
| Q2 | CUPS-Restart während submitted/printing | Status `unknown`/Retry, kein Crash | | |
| Q3 | Queue paused (`cupsdisable`) | sichtbarer Fehler, kein Silent-Fail | | |
| Q4 | Queue wieder enabled | Drain setzt fort | | |
| Q5 | Job-ID nach Restart verloren | `unknown` + Operator-Hinweis | | |
| Q6 | Max-Retries erreicht | `failed`, UI-Fehler, kein Infinite Loop | | |

---

## 6. App- / Prozess-Robustheit

| # | Szenario | Erwartung | Ergebnis | Pass/Fail |
| --- | --- | --- | --- | --- |
| A1 | App-Neustart mit offenen Orders + Auto-Print | **kein** Doppel-Auto-Job (Ledger) | | |
| A2 | Nachdruck nach Neustart | genau ein neuer Job `is_reprint=1` | | |
| A3 | App-Crash mid-job, Restart | Recovery / kein Doppeldruck Auto | | |
| A4 | RIKER offline | Status offline, letzte Liste bleibt | | |
| A5 | RIKER wieder online | Poll reset, Diff korrekt | | |
| A6 | Complete-Button | asynchron, kein UI-Freeze; Druckstatus unverändert | | |
| A7 | Doppelklick Complete | nur ein In-Flight / soft-idempotent | | |
| A8 | Routing: eine Order → mehrere Rollen-Jobs | Jobs je Regel | | |

---

## 7. Latitude 5285 / Kiosk

| # | Szenario | Erwartung | Ergebnis | Pass/Fail |
| --- | --- | --- | --- | --- |
| K1 | Vollbild nach Login/Autostart | Kiosk | | |
| K2 | Touch-Targets bedienbar | ≥ 48–64 px | | |
| K3 | Kein Screen-Blank (DPMS off) | 30+ min | | |
| K4 | Statusleiste Farben lesbar | RIKER/PICARD/Drucker | | |
| K5 | 30+ min Dauer-Polling | kein UI-Freeze | | |
| K6 | 4 h Dauerbetrieb (V1.0 DoD) | kein Crash, kein Doppeldruck | | |

---

## 8. Parallelbetrieb / Cutover-Smoke

| # | Szenario | Erwartung | Ergebnis | Pass/Fail |
| --- | --- | --- | --- | --- |
| M1 | Nur **ein** Client mit Auto-Print aktiv | kein Doppeldruck Alt+Neu | | |
| M2 | Schattenbetrieb: SPOCK2 druckt, Alt nur Anzeige | Layout/Routing OK | | |
| M3 | Rollback: Alt-Client startklar | dokumentiert | | |

---

## Zusammenfassung

| Bereich | Pass | Fail | N/A / DEF | Gesamtstatus |
| --- | --- | --- | --- | --- |
| Basisdruck | | | | |
| Layout/Zeichensatz | | | | |
| Cutter/Papier | | | | |
| Replug/Zuordnung | | | | |
| CUPS-Robustheit | | | | |
| App-Robustheit | | | | |
| Kiosk/Latitude | | | | |
| Parallel/Cutover | | | | |

**Phase-7-Gesamt:** ☐ Pass ☐ Pass mit offenen Punkten ☐ Fail  

**Offene Punkte / Follow-ups:**

| ID | Beschreibung | Owner | Zielphase |
| --- | --- | --- | --- |
| | | | |

**Freigabe für Phase 8/9:** ☐ ja ☐ nein **Unterschrift:** _______________ **Datum:** _______________
