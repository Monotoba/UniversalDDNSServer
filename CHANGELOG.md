# Changelog

All notable changes are recorded here. No stable release exists.

## [Unreleased]
### Added
- RFC 2136/TSIG TCP update adapter for A/AAAA resource record sets using dnspython.
- Signed update construction, cross-zone restriction, error handling, and unit tests.
- Authorization-gated update orchestration and SQLite update-intent journal.
- Python 3.11+ domain model, ports, desired-state storage and tests.

### Outstanding
- No HTTP/DDNS server, production worker, real authoritative-server integration test,
  automatic uncertain-state reconciliation, client authentication or deployment release.

## [0.0.0-design] — 2026-10-13
Initial architecture and project documentation.
