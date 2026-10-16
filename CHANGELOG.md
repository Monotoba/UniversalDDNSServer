# Changelog

All notable changes are recorded here. Published alpha versions are experimental; no stable release has been published.

## [0.4.0a1] — 2026-10-16 (published experimental prerelease)

- Catalog-managed A/AAAA templates with revision-controlled staging and scoped REST discovery/publication requests.
- Explicit active-record token provisioning, dormant grant isolation, and revocation-gated reactivation.
- Local credential blocker inventory, nonsecret reference-based revocation and complete credential metadata inventory.
- Transactional SQLite credential event history and verified local operator attribution for credential CLI issuance and revocation.
- Updated operator, API and test-VM documentation. Published from approved commit `592153ed` with wheel, source distribution and `SHA256SUMS`; see [draft release notes](docs/releases/v0.4.0a1-draft.md) and [release checklist](docs/operations/V0_4_ALPHA_RELEASE_CHECKLIST.md).

## [0.3.0a1] — 2026-10-14 (published prerelease)

- Experimental DynDNS2-compatible, scope-restricted HTTP update intake; `good` only after worker publication, `nochg` after authoritative observation, otherwise conservative transient response.
- Optional UDDNSUpdater DynDNS2 adapter and end-to-end isolated BIND 9 interoperability testing.
- Documented experimental loopback-only migration; compatibility regression for existing REST intents, idempotency and tokens.
- Remaining limitations: no public ingress, full DynDNS2 client variants, high availability or production disaster recovery.

## [0.2.0a1] — 2026-10-14

- Structured, redacted audit events for authentication, publishing, and recovery.
- Read-only operator intent inspection and authoritative reconciliation with explicit exit codes.
- Local credential inventory and documented token rotation procedure.
- Guarded VM updater with backups, startup readiness checks, verification and best-effort rollback.
- Expanded regression testing and packaged alpha artifacts with SHA-256 checksums.

## [0.1.0a1] — published prerelease

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
- Ubuntu 24.04.5 VM installation, reboot persistence, scratch SQLite restore and guarded offline restore passed; see validation evidence. Actual in-flight process termination and production disaster recovery are not validated.
- Not suitable for direct internet exposure; TLS termination and global rate limiting are not supplied.
- No first-party authoritative DNS daemon; an existing RFC 2136 server is required.
- General multi-writer conflict semantics and automated resolution of ambiguous publication outcomes remain incomplete.
- This section records the initial published experimental alpha.

## [0.0.0-design] — 2026-10-13
Initial architecture and project documentation.
