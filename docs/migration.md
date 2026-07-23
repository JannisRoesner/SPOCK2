# Migration: Alt-SPOCK → SPOCK2

**Stand:** 2026-07-23  
**Zielplattform SPOCK2:** Ubuntu 24.04 auf Dell Latitude 5285  
**Alt-SPOCK:** Tkinter-Client (lokal/Referenz), funktionaler Vertrag bleibt Orientierungsmaßstab

---

## 1. Was bleibt / was sich ändert

| Übernehmen (Verhalten/Vertrag) | Entfernen / ersetzen |
| --- | --- |
| Poll offene Orders + Complete | Tkinter-Monolith / Treeview |
| PICARD-Zettel (optional Modul) | USB-Direkt (`prefer_usb_direct`) als Default |
| Auto-Print Orders/Notes (Config) | In-Memory-Dedupe |
| Kategorie-Bonlayout-Intent | Windows-GDI als Primärpfad |
| Config-URLs, Poll-Intervalle (Vokabular) | PyInstaller als einziges Delivery |
| — | Sync-HTTP/Druck im UI-Thread |

Technisch neu: PySide6, Worker-Threads, SQLite-Druckqueue + Ledger, CUPS-Rollenqueues, `.deb`/systemd/Kiosk, strukturiertes Logging, verdrahtetes `ssl_verify`.

---

## 2. Migrationsschritte

```text
Hardware-Baseline (Phase 0)
    → SPOCK2 Staging parallel zu Alt-SPOCK
    → Schattenbetrieb (echte Bestellungen, ein Auto-Print)
    → Cutover
    → 1 Event mit Alt-Client als Fallback
    → Decommission Alt auf dem Produktivgerät
```

| Phase | Tätigkeit | Exit-Kriterium |
| --- | --- | --- |
| Baseline | USB-Serials, CUPS, udev; TSP100 ggf. deferred | Checklist ausgefüllt |
| Staging | `.deb` oder Dev-Install; Config auf Staging-RIKER/PICARD | Testprints + Poll OK |
| Parallel | Siehe [acceptance.md](acceptance.md) §2 | Kein Doppeldruck |
| Cutover | SPOCK2 führend; Alt nur Hot-Standby | Schicht stabil |
| Harden | 4 h Dauerbetrieb, Schulung | DoD V1.0 |
| Decommission | Alt vom Prod-Gerät entfernen/archivieren | Rollback-Paket noch lagernd |

---

## 3. Config-Übernahme (Orientierung)

Alt: `config.json` → Neu: TOML unter `/etc/spock2/` (Beispiel in `config/spock2.example.toml`).

| Alt-Konzept | SPOCK2 |
| --- | --- |
| RIKER-/PICARD-URLs | `[riker]` / `[picard]` Base-URLs |
| Poll-Intervall | `poll_interval_s` |
| `ssl_verify` | **wirklich verdrahtet** (ADR 0010) |
| Auto-Print Flags | getrennte Schalter Orders/Notes |
| `picard_session_id: 1` | verwerfen; aktive Sitzung per API |
| USB-Device / prefer_usb_direct | → CUPS-Queue-Namen + Profile |
| Druckername monolithisch | `station_role` + Routing-Regeln |

Bon-Design: Layout-Intent (Gruppen, DE-Labels, Mengen) beibehalten — Renderer neu, kein Copy-Paste der Alt-Architektur.

---

## 4. Daten & Zustand

- Alt-SPOCK hat **keine** persistente Druck-DB → nichts zu migrieren außer Betriebswissen.
- SPOCK2 legt SQLite-Queue/Ledger neu an (Pfad dokumentieren).
- Nach Cutover: Ledger nicht löschen (Schutz vor Doppeldruck).

---

## 5. Risiken speziell Migration

| Risiko | Gegenmaßnahme |
| --- | --- |
| Alt + Neu beide Auto-Print | Betriebsregel: nur einer aktiv |
| TSP100 noch nicht final | 5890K/CUPS-PDF zuerst; ADR 0007 offen |
| Personal gewohnt „Druck = weg“ | Schulung: Druck ≠ Erledigt |
| TLS/Self-Signed Staging | CA oder bewusstes `ssl_verify` |

---

## 6. Cutover-Tag (Kurzablauf)

1. Papier/Queues/Statusleiste prüfen.  
2. Alt-SPOCK Auto-Print **aus** (oder beenden).  
3. SPOCK2 Auto-Print **an**, Testbon je Rolle.  
4. Erste echte Orders beobachten (Routing, Umlaute, Cutter).  
5. Bei Eskalation: Rollback laut [acceptance.md](acceptance.md) §3.  
6. Nach stabilem Event: Alt nur noch Archiv/Notfallmedium.

---

## 7. Referenzen

- [acceptance.md](acceptance.md) — Abnahme & Parallelbetrieb  
- [schulung.md](schulung.md) — Operator-One-Pager  
- [hardware-checklist.md](hardware-checklist.md) / [hardware-matrix.md](hardware-matrix.md)  
- [adr/README.md](adr/README.md) — Architekturentscheidungen  
- [dev-windows.md](dev-windows.md) — Entwicklung ohne Prod-Linux
