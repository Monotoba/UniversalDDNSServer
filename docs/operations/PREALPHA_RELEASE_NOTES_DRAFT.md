# DRAFT — UniversalDDNSServer v0.1.0a1 (not published)

**Pre-alpha / experimental local deployment only.**

UniversalDDNSServer provides a Python DDNS update control plane backed by SQLite. An authenticated FastAPI endpoint accepts scoped IPv4/IPv6 A/AAAA record updates as durable intents, while an independent worker applies records to an existing authoritative server via RFC 2136/TSIG. Intent status and authoritative observation support controlled reconciliation. Local administration can issue and revoke hashed bearer tokens; queued publication revalidates authorization.

## Included
- Validated DNS A/AAAA resource record sets, managed record mapping and authorization.
- SQLite intent queue, per-principal idempotency keys, worker leases, and explicit recovery facilities.
- FastAPI PUT update and GET intent-status endpoints; client status polling.
- RFC 2136/TSIG BIND 9 adapter; local configuration, systemd examples and smoke checks.
- Isolated BIND 9 tests, separate-process API/worker tests, and integration with Monotoba/UDDNSUpdater.
- Python 3.11–3.13 test coverage.

## Explicit limitations
- No bundled authoritative DNS server; deploy a separate RFC 2136-capable server.
- No verified clean-host systemd installation or reboot and backup restoration at draft time.
- Not safe to expose directly to the internet. API defaults to 127.0.0.1; production TLS and perimeter controls are not supplied.
- Authorization, throttling and audit management are pre-alpha. Multi-writer conflict guarantees and automatic uncertain-outcome retries are incomplete.
- HTTP 202 signals durable queue acceptance, not DNS publication; observe status and authoritative DNS to verify updates.

## Installation
Consult [deployment instructions](DEPLOYMENT.md) and [release gate checklist](PREALPHA_RELEASE_CHECKLIST.md). Verify the isolated test zone and TSIG permission scope before enabling any DNS writes.

**Release status:** Draft only. No tag, artifact, or GitHub release has been published.
