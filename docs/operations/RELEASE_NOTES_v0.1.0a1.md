# UniversalDDNSServer v0.1.0a1 — Pre-alpha

**Experimental release — for isolated, loopback-only evaluation. Not production-ready or suitable for direct internet exposure.**

UniversalDDNSServer is a Python-based dynamic DNS management control plane. An authenticated FastAPI endpoint accepts per-record scoped A/AAAA update requests into a durable SQLite intent journal; a separate worker publishes authorized updates to an existing authoritative DNS server using RFC 2136 with TSIG.

## Included
- Scoped local API, hashed bearer-token administration, revocation checks before pending publication
- SQLite durable queue, idempotency, worker leases and reconciliation
- BIND 9 RFC 2136/TSIG backend and authoritative observation
- Local Ubuntu systemd service units, test kit, backup/restore and recovery validation tools
- UDDNSUpdater interoperability tests
- Python 3.11–3.13 CI; candidate wheel and source distribution

## Validated
- Ubuntu 24.04.5 disposable VM install, real authenticated publication and authoritative DNS verification
- Reboot and systemd service recovery
- Online backup, scratch restore, full stopped-service database restoration with verified permissions
- Pending update recovery after worker restart, idempotent submission
- BIND TSIG permission limited to the intended host; authorized publication succeeds; unauthorized signed updates refused
- Simulated post-publication timeout reconciles without a duplicate application write

## Known limitations
- Not an authoritative DNS server; requires a separately configured RFC 2136-capable authoritative server
- No production reverse proxy/TLS, public deployment security approval, mature log-retention policy or distributed rate limiting
- Genuine SIGKILL during an in-flight RFC 2136 publication and adverse transport faults **have not been exercised**; do not infer exactly-once publication guarantees
- Concurrent third-party authoritative writers, ambiguous failures, automatic retry and production disaster recovery are not comprehensively supported
- HTTP 202 indicates queued, not published. Check intent status and authoritative DNS.
- DNS records do not bypass firewall/NAT/CGNAT limitations

See [deployment guide](https://github.com/Monotoba/UniversalDDNSServer/blob/main/docs/operations/DEPLOYMENT.md), [VM evidence](https://github.com/Monotoba/UniversalDDNSServer/blob/main/docs/operations/VM_VALIDATION_2026-10-14.md), and [security review](https://github.com/Monotoba/UniversalDDNSServer/blob/main/docs/operations/SECURITY_REVIEW_2026-10-14.md).

Distributed as a GitHub prerelease with wheel and source-distribution artifacts.
