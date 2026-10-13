# Implementation plan

Phases are engineering milestones, not release dates.

## Phase 0 — design and groundwork
- [x] Architecture proposal, ADR-0001 and ADR-0002.
- [x] Core RRset model, interfaces and SQLite desired-state persistence.
- [x] Authorization-gated intent orchestration and SQLite intent journal.
- [x] First unit tests and Python CI.
- [ ] Generalized DNS RRset type design ADR and durable schema migration strategy.

## Phase 1 — secure real DNS publication
- [ ] Securely bind principal identity to request entry points; define least-privilege policy/token storage.
- [x] Add durable intent-state reconciliation against authoritative DNS and explicit retries.\n- [ ] Add a worker lifecycle, per-record ownership leases and crash-safe concurrent recovery.
- [x] Persist per-principal request idempotency keys with conflicting-payload checks.\n- [ ] Add backend retry classification, bounded scheduling and conditional DNS update semantics.
- [x] Implement RFC 2136/TSIG adapter and isolated BIND 9 A/AAAA, replacement and negative integration tests.
- [ ] Coordinate journal and desired-state storage consistently across failures.
- [ ] Implement authenticated HTTPS REST transport and rate limiting.

## Phase 2 — usability
- [ ] DynDNS2 client compatibility, deployment, backup/restore and integration with UDDNSUpdater.

## Phase 3 — management
- [ ] Roles, groups, audited activity and browser management interface.

## Phase 4 — plugins
- [ ] Backend capability negotiation, provider adapters, versioned SDK and contract tests.

Every functional change needs tests, docs and CI.
