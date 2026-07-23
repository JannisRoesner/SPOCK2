# Abnahmekriterien SPOCK2 (Phase 9)

**Ziel:** Formale Abnahme von V1.0 vor Cutover, inkl. Parallelbetrieb, Rollback und Schulung.  
**Datum Abnahme:** _______________ **Version:** _______________ **Abnehmer:** _______________

Verwandt: [hardware-matrix.md](hardware-matrix.md), [schulung.md](schulung.md), [migration.md](migration.md), [adr/README.md](adr/README.md).

---

## 1. Definition of Done V1.0 (Checkliste)

| # | Kriterium | Nachweis | OK |
| --- | --- | --- | --- |
| D1 | Alle funktionalen Anforderungen (Orders, Complete, Auto-Print, Nachdruck, 3 Queues, Queue/Dedup, optional PICARD) | Testprotokoll | ☐ |
| D2 | UI-Thread frei von HTTP/Druck | Code-Review / Smoke unter Last | ☐ |
| D3 | 4 h Dauerbetrieb ohne Crash und ohne Doppel-Auto-Druck | Log + Beobachtung | ☐ |
| D4 | `.deb`-Install → Login → Kiosk → Testprint | Installationsprotokoll | ☐ |
| D5 | Hardwarematrix Phase 7 ohne kritischen Fail | [hardware-matrix.md](hardware-matrix.md) | ☐ |
| D6 | Parallel-Cutover einmal erfolgreich | Abschnitt 2 | ☐ |
| D7 | Schulungsblatt 1 Seite vorhanden und durchgegangen | [schulung.md](schulung.md) | ☐ |
| D8 | ADRs 0001–0012 geschrieben (0007 ggf. Proposed) | [adr/](adr/) | ☐ |
| D9 | Rollback-Pfad getestet oder Dry-Run | Abschnitt 3 | ☐ |
| D10 | Keine Secrets in Logs; `ssl_verify` verdrahtet | Spot-Check | ☐ |

**Gesamtergebnis DoD:** ☐ Pass ☐ Fail

---

## 2. Parallelbetrieb

### Regeln

1. **Nur ein Client** darf `auto_print` für Orders (und Notes) aktiv haben.
2. Bevorzugt: SPOCK2 auf Latitude; Alt-SPOCK auf zweitem Gerät **nur Anzeige** oder Auto-Print aus.
3. Schattenbetrieb: echte Bestellungen, Layout/Routing vergleichen, Complete nur auf dem führenden Client.

### Parallel-Checkliste

| # | Schritt | Soll | OK |
| --- | --- | --- | --- |
| P1 | Alt-SPOCK Auto-Print deaktiviert **oder** Alt aus | kein Doppelbon | ☐ |
| P2 | SPOCK2 Auto-Print an, Queues korrekt | Bons an richtiger Rolle | ☐ |
| P3 | Mind. 10 echte/ Staging-Orders | Layout Parität Intent | ☐ |
| P4 | PICARD-Zettel (falls Prod) | Empfang/Druck/Schließen | ☐ |
| P5 | Complete nur SPOCK2 | RIKER-Liste konsistent | ☐ |
| P6 | Neustart SPOCK2 mid-shift | kein Doppel-Auto-Druck | ☐ |
| P7 | Operator-Feedback dokumentiert | offene Punkte Liste | ☐ |

**Schattenbetrieb von:** _______________ **bis:** _______________  
**Ergebnis Parallel:** ☐ Pass ☐ Pass mit Punkten ☐ Fail

---

## 3. Rollback

| Trigger | Aktion | Verantwortlich | OK |
| --- | --- | --- | --- |
| Kritischer Druckausfall | CUPS/Queues prüfen; ggf. Alt-SPOCK starten | | ☐ |
| App-Crash-Schleife | `systemctl --user stop spock2`; Alt-Client | | ☐ |
| Falsches Routing / Doppeldruck | Auto-Print SPOCK2 aus; Alt übernehmen | | ☐ |
| Paket-Regression | `spock2-prev` / vorherige `.deb` | | ☐ |

**Rollback-Dry-Run durchgeführt:** ☐ ja ☐ nein **Dauer bis Alt bereit:** _____ min  

Config unter `/etc/spock2/` bleibt; Queue-DB-Pfad notieren: _______________

---

## 4. Funktionale Abnahme (Kurz)

| Bereich | Pflichtfälle | OK |
| --- | --- | --- |
| RIKER Poll + Offline-Cache | Timeout, 500, Bad JSON → Status, keine stille leere Liste | ☐ |
| Complete | Erfolg, Doppelklick, Offline-Fehler sichtbar | ☐ |
| Auto-Print | neue Order → Jobs; Restart → kein Duplikat | ☐ |
| Nachdruck | `is_reprint=1`, physischer Bon | ☐ |
| Routing | Multi-Rollen laut Config | ☐ |
| PICARD | enabled/disabled; aktive Sitzung; Auto-Print Notes | ☐ |
| Statusleiste | RIKER / PICARD / Drucker / Queue Farben | ☐ |
| Admin | Testprint, URLs, Auto-Print-Schalter | ☐ |

---

## 5. Schulung One-Pager — Outline

Das Operator-Blatt ([schulung.md](schulung.md)) muss mindestens abdecken:

1. Start / Kiosk / was die Statusfarben bedeuten  
2. Bestellkarte lesen (Tisch, Artikel, Notizen, Wartezeit)  
3. **Auto-Print ≠ Erledigt**  
4. Nachdruck vs. neuer Bon  
5. Erledigt tippen (wann, Bestätigung)  
6. Zettel (PICARD), falls aktiv  
7. Papier/Stau/Drucker-aus → wen rufen  
8. Notfall: Alt-SPOCK / Rollback-Kontakt  

**Schulung durchgeführt:** ☐ ja **Teilnehmer:** _______________ **Datum:** _______________

---

## 6. Cutover-Freigabe

| Frage | Ja/Nein |
| --- | --- |
| Phase-7-Matrix freigegeben? | |
| Parallelbetrieb ohne kritischen Doppeldruck? | |
| Rollback innerhalb akzeptabler Zeit? | |
| Schulung erledigt? | |
| TSP100-ADR 0007 Accepted oder bewusst deferred mit Workaround? | |

**Go-Live SPOCK2:** ☐ freigegeben ☐ nicht freigegeben  

**Unterschriften:** Abnehmer _______________ Technik _______________ Datum _______________
