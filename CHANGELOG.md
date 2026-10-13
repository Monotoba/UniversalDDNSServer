# Changelog

All notable changes are recorded here. No stable release exists.

## [Unreleased]
### Added
- Isolated BIND 9 authoritative server integration tests for signed A/AAAA RRset publication.
- Authoritative RRset observation, restart reconciliation and opt-in verified retries.
- Persisted per-principal idempotency keys with payload conflict detection.
- Ruff, scoped mypy, SQLite integration, Python matrix CI.
- RFC 2136/TSIG adapter, journal/orchestration, SQLite state store and core interfaces.

### Limitations
- Still no authenticated HTTP service, production worker or deployment.
- Recovery requires explicit invocation; safe multi-writer conditional updates and
  lease management are not implemented.

## [0.0.0-design] — 2026-10-13
Initial architecture and project documentation.
