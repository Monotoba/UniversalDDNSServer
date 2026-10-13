# Changelog

All notable changes are recorded here. No stable release exists.

## [Unreleased]
### Added
- Ruff lint and scoped mypy static type checking.
- Dedicated GitHub Actions workflows for quality and SQLite integration tests.
- A real SQLite restart/publish workflow integration test with a fake DNS provider.
- RFC 2136/TSIG TCP update adapter for A/AAAA record sets using dnspython.
- Authorization-gated update orchestration and SQLite update-intent journal.
- Python 3.11+ domain model, ports, desired-state storage and tests.

### Outstanding
- No HTTP/DDNS server, production worker, real authoritative-server integration test,
  automatic uncertain-state reconciliation, client authentication or deployment release.

## [0.0.0-design] — 2026-10-13
Initial architecture and project documentation.
