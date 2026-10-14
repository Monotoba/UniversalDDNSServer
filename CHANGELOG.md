# Changelog

All notable changes are recorded here. No stable release or GitHub pre-alpha release has been published.

## [Unreleased] — candidate for v0.1.0a1 (not tagged)

### Added
- Validated A/AAAA record sets, SQLite persistence, and durable intent queue with per-principal idempotency.
- Scoped FastAPI update intake and status API, persistent hashed tokens, local token issuance and revocation.
- Publication worker with bounded recovery, leases and authorization revalidation before publication.
- RFC 2136/TSIG DNS publication and authoritative observation against isolated BIND 9.
- Experimental local Linux runtime, configuration validation, systemd examples and installation smoke checks.
- Real localhost HTTP / separate worker / BIND 9 integration with Monotoba/UDDNSUpdater.
- Unit tests on Python 3.11–3.13, BIND integration matrix on Python 3.11–3.13, Ruff and scoped mypy.
- Pre-alpha draft release notes and explicit clean-host validation checklist.

### Known limitations
- Clean Ubuntu systemd installation, reboot persistence and backup/restore are not yet validated.
- Not suitable for direct internet exposure; TLS termination and global rate limiting are not supplied.
- No first-party authoritative DNS daemon; an existing RFC 2136 server is required.
- General multi-writer conflict semantics and automated resolution of ambiguous publication outcomes remain incomplete.
- This section is *not* a published release record.

## [0.0.0-design] — 2026-10-13
Initial architecture and project documentation.
