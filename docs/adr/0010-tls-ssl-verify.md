# ADR 0010: TLS- und `ssl_verify`-Policy

- **Status:** Accepted
- **Datum:** 2026-07-23
- **Entscheider:** SPOCK2-Architektur (Phase 0)

## Context

Im Alt-SPOCK existierte `ssl_verify` in der Config, war aber **nicht verdrahtet**; Clients defaulteten auf Verify=True bzw. verhielten sich inkonsistent. RIKER/PICARD laufen aktuell oft ohne Auth im LAN; TLS kann trotzdem mit privaten CAs oder absichtlich deaktiviertem Verify vorkommen. Stille Fehleinstellungen sind ein Sicherheits- und Support-Risiko.

## Decision

1. `ssl_verify` ist in der TOML **explizit** und wird von **httpx-Clients verdrahtet**.
2. Default in Example-/Prod-Templates: **`ssl_verify = true`** (System-CA-Store).
3. Für private CAs: System-Trust erweitern oder CA-Bundle-Pfad in Config (wenn implementiert) — nicht „einfach false“ als Dauerlösung.
4. `ssl_verify = false` nur für lab/dev oder bewusst dokumentierte Notfälle; UI/Admin zeigt Warnhinweis.
5. TLS-Fehler sind typisiert (`TlsError`) und erscheinen in der Statusleiste — kein stilles `[]`.
6. Keine Secrets (Tokens, falls später) in Logs; URLs ohne Credentials loggen.

## Consequences

### Positiv

- Vorhersagbares TLS-Verhalten; weniger „works on my machine“.
- Klare Ops-Doku für CA-Probleme.

### Negativ / Risiken

- Striktes Verify kann Staging mit Self-Signed blockieren → bewusst false oder CA installieren.
- Spätere Auth-Einführung braucht erneutes ADR.

### Follow-up

- Phase 1/2: Config-Modell + Client-Tests (Verify on/off, bad cert).
- Deploy-Doku: CA auf Latitude installieren.
