# Implementation plan

Each phase ends in tests, docs and a local Git commit. No phase promises a calendar deadline.

## Phase 0 — design baseline
- Define architecture and ADR, threat model, standards, REST contract, plugin policies, CI and documentation.
- Acceptance: docs cross-reference correctly; license present; design issues recorded.

## Phase 1 — minimal secure core
- Define domain objects and ports; SQLite adapter with migrations; policy/token validator.
- Implement HTTPS REST address update, RFC 2136 TSIG adapter and orchestration.
- Test invalid hostname/IP, unauthorized update, no-op, concurrent updates, backend timeouts, crash recovery and secret redaction.
- Acceptance: end-to-end A/AAAA integration against isolated DNS server; failed authentication causes no mutation.

## Phase 2 — operator usability
- DynDNS2 protocol adapter with compatibility matrix; CLI/config validation; systemd; container images; backup/restore.
- Acceptance: existing compatible router/client updates through scoped auth; clean install and restore documented.

## Phase 3 — management
- Web interface, multi-user roles, device grouping, token rotation, audit filtering.
- Acceptance: cross-tenant isolation tests; least privilege demonstrated.

## Phase 4 — extensibility
- Additional DNS API adapters; stable plugin SDK / conformance tests; events/webhooks; Prometheus metrics; monitoring.
- Acceptance: third-party adapter passes compatibility suite without changes to core.

## Future
Private DNS integration, WireGuard endpoint helpers, HA design, external identity providers, multiple persistence adapters.

## Engineering gates
Unit and integration tests are required on every functional PR. Static analysis, dependency checks, linting, coverage reports, schema contract validation and reproducible builds should be automated in CI. Security review is required before any production release.
