# Architecture Decision Records (ADR) — SPOCK2

Index der Architekturentscheidungen für SPOCK2. Format je ADR: **Status**, **Datum**, **Context**, **Decision**, **Consequences**.

**Konvention:** Dateiname `NNNN-kurz-titel.md`, Nummer fortlaufend. Status typisch: `Proposed` · `Accepted` · `Deprecated` · `Superseded by NNNN`.

## Übersicht

| Nr. | Titel | Status | Datum |
| --- | --- | --- | --- |
| [0001](0001-cups-vs-usb.md) | CUPS vs. Direct-USB | Accepted | 2026-07-23 |
| [0002](0002-pyside6-workers.md) | PySide6-Worker-Modell | Accepted | 2026-07-23 |
| [0003](0003-print-status-semantics.md) | Print-Statussemantik | Accepted | 2026-07-23 |
| [0004](0004-dedup-ledger.md) | Dedup-/Ledger-Strategie | Accepted | 2026-07-23 |
| [0005](0005-printer-roles-routing.md) | Printer-Rollen und Routing | Accepted | 2026-07-23 |
| [0006](0006-picard-scope-v1.md) | PICARD-Scope V1 | Accepted | 2026-07-23 |
| [0007](0007-tsp100-driver-strategy.md) | TSP100-Treiberstrategie | Proposed (pending hardware) | 2026-07-23 |
| [0008](0008-pos5890k-profile.md) | POS 5890K-Profil | Accepted | 2026-07-23 |
| [0009](0009-packaging-systemd-kiosk.md) | Packaging / systemd / Kiosk | Accepted | 2026-07-23 |
| [0010](0010-tls-ssl-verify.md) | TLS / `ssl_verify` | Accepted | 2026-07-23 |
| [0011](0011-polling-no-websocket-v1.md) | Polling, kein WS/SSE in V1 | Accepted | 2026-07-23 |
| [0012](0012-no-autocomplete-after-print.md) | Kein Auto-Complete nach Druck | Accepted | 2026-07-23 |

## Leitentscheidungen (Kurz)

1. PySide6-Desktop-Kiosk, Linux/`.deb` primär.
2. CUPS einziger Produktiv-Druckpfad; PyUSB nur Diagnose.
3. SQLite-Queue + Ledger gegen Doppeldruck.
4. Druck ≠ Erledigt (Default).
5. Worker/Signale statt Sync-IO im UI.
6. Rollen-Queues + Hybrid-Routing.
7. PICARD optional, in V1 implementiert.
8. Polling V1; kein WebSocket-Zwang.

## Verwandte Docs

- [Hardware-Checklist (Phase 0)](../hardware-checklist.md)
- [Hardware-Matrix (Phase 7)](../hardware-matrix.md)
- [Abnahme (Phase 9)](../acceptance.md)
- [Migration](../migration.md)
- [Windows-Entwicklung](../dev-windows.md)
