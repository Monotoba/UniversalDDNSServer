# Changelog

All notable changes will be recorded here. There is no stable release.

## [Unreleased]
### Added
- ADR-0002 selecting Python 3.11+ and FastAPI for a future HTTP adapter.
- Core-owned versioned interfaces for DNS backends, state persistence, authorization and events.
- Immutable validated A/AAAA resource record set domain model.
- Transactional SQLite desired-state adapter with version guard, idempotent updates and deletion.
- Initial domain and SQLite unit tests and Python CI matrix.

### Not yet implemented
- HTTP server, DDNS-compatible endpoints, user/token authentication, DNS publication and operational deployment.

## [0.0.0-design] — 2026-10-13
Initial design and open-source documentation baseline.
