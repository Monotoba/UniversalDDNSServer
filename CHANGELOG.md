# Changelog

All notable changes will be recorded here. No stable release exists.

## [Unreleased]
### Added
- Authorization-gated update orchestration with core-owned backend interfaces.
- Durable SQLite update-intent journal with pending/applying/applied/failed states.
- Partial unique index preventing competing active updates to the same RRset.
- Tests for denied requests, application, backend failure and crash-ambiguous state.
- ADR-0002, Python domain model, SQLite desired-state adapter and core tests.

### Limitations
- No operational HTTP/DDNS server or real DNS backend; no automatic recovery of applying intents, per-client idempotency, or production credentials.

## [0.0.0-design] — 2026-10-13
Initial design baseline and OSS policies.
