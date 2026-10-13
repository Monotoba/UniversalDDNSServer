# Implementation plan

Milestone phases are sequencing guides, not promised delivery dates.

## Phase 0 — design and infrastructure (in progress)
- [x] Initial proposal, modular architecture, threat model, standards references, developer documentation.
- [x] ADR-0002 language/framework decision.
- [x] Define core persistence, DNS provider, authorization and event ports.
- [x] First SQLite desired-state adapter and unit tests.
- [ ] Finalize generalized DNS RRset ADR and typed record handler strategy.
- [ ] Review security and schema semantics for production requirements.

## Phase 1 — secure DDNS publishing core
- [ ] Add typed error categories, transactional update-intent/outbox and crash reconciliation.
- [ ] Add request orchestration with strict per-record authorization and idempotency.
- [ ] Implement testable RFC 2136/TSIG DNS adapter and its contract suite.
- [ ] Implement FastAPI transport with scoped-token authentication and rate limiting.
- [ ] Test A/AAAA publication against isolated authoritative DNS and failure paths.
- [ ] Add configuration validation and complete operational docs.

## Phase 2 — usability and compatibility
- [ ] DynDNS2 adapter, systemd/container deployment, backup/restore and UDDNSUpdater compatibility tests.

## Phase 3 — management
- [ ] Multi-user roles, device groups, web management UI, token rotation and audit log queries.

## Phase 4 — plugin integrations
- [ ] Versioned SDK, backend capability negotiation, additional DNS providers, event sinks and monitoring.

## Future
Private-zone automation, generalized DNS RRsets and record-type-specific authorization, WireGuard helpers, HA and additional stores.

For each behavior change: tests, docs, CI, local Git commit, and compatibility assessment.
