# Hardware-Vorabchecklist (Phase 0)

**Gerät:** Dell Latitude 5285 (Ubuntu 24.04 LTS, Zielplattform)  
**Drucker:** 2× Star TSP100 (80 mm), 1× POS 5890K (58 mm)  
**Datum:** _______________ **Tester:** _______________ **Build/Config:** _______________

## Zweck

Diese Checkliste dokumentiert die Hardware-Baseline vor der Implementierung und vor Phase-7-Abnahmen. Ergebnisse sind Voraussetzung für Treiber-ADRs (`0007`, `0008`) und stabile CUPS-Zuordnung.

## Priorität / Aufschub

| Bereich | Priorität | Hinweis |
| --- | --- | --- |
| Latitude 5285, Touch, Kiosk, Netz | hoch | sofort |
| POS 5890K + CUPS-PDF | hoch | kann als erster Druckpfad genutzt werden |
| CUPS-Queues, udev, Diagnose-CLI | hoch | auch ohne TSP100 testbar (CUPS-PDF / Fake) |
| 2× Star TSP100 | mittel | **darf aufgeschoben werden**, bis Hardware verfügbar ist |

> **Hinweis:** TSP100-Tests (Serial, Cutter, Vertauschungsschutz) können warten. Entwicklung und Integration starten mit **POS 5890K** und/oder **CUPS-PDF**-Queues (`spock-kitchen`, `spock-counter`, `spock-small`).

---

## 1. Host / Latitude 5285

| # | Prüfung | Soll | Ist / Notiz | OK |
| --- | --- | --- | --- | --- |
| H1 | OS-Version | Ubuntu 24.04 LTS | | ☐ |
| H2 | Architektur | x86_64 | | ☐ |
| H3 | Display | ~12,3", 1920×1280, Touch aktiv | | ☐ |
| H4 | Touch-Ziele ≥ 48–64 px in Test-UI | Lesbar, bedienbar | | ☐ |
| H5 | Vollbild / Kiosk-Flag | Fenster füllt Bildschirm | | ☐ |
| H6 | DPMS / Screensaver aus (Kiosk-Script) | Kein Blank während Schicht | | ☐ |
| H7 | Netz: RIKER erreichbar | `GET /api/menu` oder Orders OK | | ☐ |
| H8 | Netz: PICARD erreichbar (falls genutzt) | `GET /api/aktive-sitzung` OK | | ☐ |
| H9 | User in Gruppe `lp` | Druck ohne Root | | ☐ |
| H10 | USB-Hub aktiv gespeist | Stabil unter Last | | ☐ |

**Ergebnis Host**

| Feld | Wert |
| --- | --- |
| Hostname | |
| Kernel | |
| Ergebnis (Pass/Fail/Teil) | |
| Blocker | |

---

## 2. USB-Inventar (alle Drucker)

Befehle (Referenz):

```bash
lsusb
lsusb -v 2>/dev/null | less
udevadm info -a -n /dev/usb/lp0
python -m spock2.diagnostics.probe_usb   # sobald CLI existiert
```

| Gerät | Vendor:Product | Serial | Kernel-Node | by-path | by-id | Notiz | OK |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TSP100 #1 (Kitchen) | | | | | | ggf. aufgeschoben | ☐ |
| TSP100 #2 (Counter) | | | | | | ggf. aufgeschoben | ☐ |
| POS 5890K (Small) | | | | | | | ☐ |
| CUPS-PDF (Dev) | n/a | n/a | n/a | n/a | n/a | virtuell | ☐ |

**Annahme zu prüfen:** Beide TSP100 haben **auslesbare, unterschiedliche** USB-Seriennummern. Falls nicht → udev by-path + Kabelbeschriftung (siehe Risiken im Entwicklungsplan).

---

## 3. CUPS-Queues

Soll-Queues:

| Queue-Name | Rolle | Profil | Physisches Ziel (Prod) | Dev-Ersatz |
| --- | --- | --- | --- | --- |
| `spock-kitchen` | kitchen | tsp100 | TSP100 #1 | CUPS-PDF / 5890K |
| `spock-counter` | counter | tsp100 | TSP100 #2 | CUPS-PDF / 5890K |
| `spock-small` | small | pos5890k | POS 5890K | CUPS-PDF / 5890K |

| # | Prüfung | Soll | Ist / Notiz | OK |
| --- | --- | --- | --- | --- |
| C1 | `cupsd` läuft | active | | ☐ |
| C2 | Queue `spock-kitchen` angelegt | idle/enabled | | ☐ |
| C3 | Queue `spock-counter` angelegt | idle/enabled | | ☐ |
| C4 | Queue `spock-small` angelegt | idle/enabled | | ☐ |
| C5 | Device-URI enthält Serial oder by-path | stabil nach Replug | | ☐ |
| C6 | Testseite je Queue (`lp -d …`) | Job completed | | ☐ |
| C7 | App kennt nur Queue-Namen | kein `/dev/usb/lp*` in Config | | ☐ |
| C8 | CUPS-PDF als Ersatzqueue dokumentiert | Dev/CI möglich | | ☐ |

**Ergebnis CUPS**

| Queue | URI | Treiber/PPD | Testseite | Pass/Fail |
| --- | --- | --- | --- | --- |
| spock-kitchen | | | | |
| spock-counter | | | | |
| spock-small | | | | |

---

## 4. udev-Regeln

Ziel: stabile Symlinks, z. B. `/dev/spock-kitchen`, `/dev/spock-counter`, `/dev/spock-small`.

| # | Prüfung | Soll | Ist / Notiz | OK |
| --- | --- | --- | --- | --- |
| U1 | Regeldatei installiert | z. B. `99-spock-printers.rules` | | ☐ |
| U2 | Symlink by-serial (bevorzugt) | vorhanden | | ☐ |
| U3 | Fallback by-path | dokumentiert, falls Serial fehlt | | ☐ |
| U4 | Replug → gleicher Symlink | Queue bleibt korrekt | | ☐ |
| U5 | Vertauschungsschutz 2× TSP100 | Kitchen/Counter vertauschen sich nicht | ☐ / aufgeschoben | ☐ |

**Ergebnis udev**

| Symlink | ATTRS{serial} / KERNELS path | Nach Replug stabil? | Pass/Fail |
| --- | --- | --- | --- |
| /dev/spock-kitchen | | | |
| /dev/spock-counter | | | |
| /dev/spock-small | | | |

---

## 5. POS 5890K (früh testbar)

| # | Prüfung | Soll | Ist / Notiz | OK |
| --- | --- | --- | --- | --- |
| P1 | USB-ID dokumentiert | Vendor/Product bekannt | | ☐ |
| P2 | Minimalbon ESC/POS oder Raster | lesbar | | ☐ |
| P3 | Umlaute / € | korrekt | | ☐ |
| P4 | Lange Artikelnamen / Wrap | kein Overflow-Chaos | | ☐ |
| P5 | Cutter | meist **kein** Partial-Cut; Verhalten notieren | | ☐ |
| P6 | QR als Bitmap (falls genutzt) | scannbar / akzeptabel | | ☐ |
| P7 | An Queue `spock-small` gebunden | Replug OK | | ☐ |

**Ergebnis 5890K:** Pass / Fail / Teil **Notizen:** _______________

---

## 6. Star TSP100 (kann aufgeschoben werden)

Nur ausfüllen, wenn Hardware vor Ort ist. Sonst Status: **DEFERRED**.

| # | Prüfung | Soll | Status | OK |
| --- | --- | --- | --- | --- |
| T1 | Serial #1 auslesbar und eindeutig | ja | DEFERRED / | ☐ |
| T2 | Serial #2 auslesbar und eindeutig | ja, ≠ #1 | DEFERRED / | ☐ |
| T3 | Treiberstrategie gewählt | CUPS-Filter vs. Raw-Raster (ADR 0007) | DEFERRED / | ☐ |
| T4 | Testbon 80 mm | Layout lesbar | DEFERRED / | ☐ |
| T5 | Cutter | Bon getrennt | DEFERRED / | ☐ |
| T6 | Umlaute / € | korrekt | DEFERRED / | ☐ |
| T7 | Replug gleiche Queue | Job landet am richtigen Gerät | DEFERRED / | ☐ |
| T8 | Vertauschungsschutz | Serial oder by-path | DEFERRED / | ☐ |

**Ergebnis TSP100:** Pass / Fail / **DEFERRED** **Begründung:** _______________

---

## 7. CUPS-PDF / Entwicklungsersatz

| # | Prüfung | Soll | Ist / Notiz | OK |
| --- | --- | --- | --- | --- |
| D1 | `cups-pdf` oder vergleichbare Testqueue | installiert | | ☐ |
| D2 | Drei logische Queues → PDF-Ausgabe | Dateien unterscheidbar | | ☐ |
| D3 | pycups-Submit aus App/Diagnose | Job-ID zurück | | ☐ |
| D4 | Status-Polling (`lpstat`/IPP) | Statusübergänge sichtbar | | ☐ |

---

## 8. Robustheit (Smoke)

| # | Prüfung | Soll | Ist / Notiz | OK |
| --- | --- | --- | --- | --- |
| R1 | USB-Replug während idle | Queue recovered | | ☐ |
| R2 | `systemctl restart cups` während/nach Job | App: `unknown`/Retry, kein Crash | | ☐ |
| R3 | Netzausfall RIKER | Offline-Status, Cache bleibt | | ☐ |
| R4 | ≥ 30 min Polling | kein UI-Freeze | | ☐ |

---

## Gesamtergebnis Phase 0

| Block | Ergebnis | Freigabe für |
| --- | --- | --- |
| Host Latitude | | Phase 1–3, 8 (Kiosk-Prototyp) |
| CUPS + udev + PDF | | Phase 4–5 |
| POS 5890K | | Phase 5 Profil `pos5890k` |
| TSP100 | DEFERRED / | Phase 7 / ADR 0007 final |

**Gesamtstatus Phase 0 Hardware:** ☐ Pass ☐ Pass mit Einschränkungen ☐ Fail ☐ TSP100 deferred  

**Unterschrift Tester:** _______________ **Datum:** _______________
