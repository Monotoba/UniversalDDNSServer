# v0.3.0a1 — DynDNS2 compatibility and client usability

**Status:** Issues #4–#6 complete; v0.3.0a1 release gate (#7) remains pending. Not tagged or published. This milestone implements the Phase 2 usability work in the original [implementation plan](../IMPLEMENTATION_PLAN.md), rather than revisiting the completed v0.2 audit/recovery scope.

## Deliverables in order

1. [#4 DynDNS2-compatible update transport](https://github.com/Monotoba/UniversalDDNSServer/issues/4). Authenticated, record-scoped compatibility endpoint backed by existing durable intent journal and publishing worker. Define a supported subset and return response codes accurately.
2. [#5 UDDNSUpdater interoperability](https://github.com/Monotoba/UniversalDDNSServer/issues/5). Configuration documentation and repeatable isolated cross-client test against BIND 9.
3. [#6 Installation and migration usability](https://github.com/Monotoba/UniversalDDNSServer/issues/6). Example configuration, backward-compatible local upgrade path and troubleshooting.
4. [#7 Fixed alpha release gate](https://github.com/Monotoba/UniversalDDNSServer/issues/7). Consistent `0.3.0a1` metadata, static/unit/integration CI, wheel+sdist checksums and owner-approved release.

## Acceptance principles

- Preserve the REST v1 API, policy checks, token safety and worker-only DNS publication.
- DynDNS2 requests may be accepted into the durable queue; this is **not** proof of completed authoritative publication. Explicitly document this semantic difference and avoid claiming full DynDNS2 compatibility.
- Test authorized writes and unauthorized denials against isolated BIND 9; maintain Python 3.11–3.13 test coverage.
- Keep API loopback-only for the experimental deployment; public ingress/TLS are separately planned security work.
- Report unsupported DynDNS2 options explicitly; no accidental DNS update through unrecognized record mappings.
- The release commit must pass the existing CI plus the dedicated DynDNS2 contract test; no expanding production certification gate.
- Do not publish tags or releases without explicit owner approval.

## Deferred

Generalized RRset types, transactional migration framework, production HTTPS exposure, distributed limiting, router-specific protocol quirks, a bundled authoritative server, management UI, provider adapters, high availability and full disaster recovery certification.

## Next action

Complete Issue #7 packaging and prerelease verification after the successful functional and migration-usability work; require explicit owner approval before publishing.

## Issue #5 implementation status (2026-10-14)

UDDNSUpdater now provides a discoverable `UniversalDDNSDynDNS2` adapter in `providers/provider_universalddns_dyndns2.py`, alongside the existing intent-aware REST adapter. The server CI pins UDDNSUpdater revision `2377a52c109dbb43cf624b147eaaf2483232db87`. Cross-repository isolated BIND 9 tests cover verified publication, unchanged responses, and denial of invalid credentials; the unchanged REST adapter remains tested. Both repositories' CI suites passed on this implementation. Issue #5 is closed. Next: Issue #6 installation and migration usability.

## Issue #6 completion (2026-10-14)

Published an [experimental v0.3 local upgrade and troubleshooting guide](V0_3_LOCAL_UPGRADE.md), linked it from the README and added regression coverage ensuring pre-existing SQLite credentials, durable REST intents and idempotency keys survive startup with DynDNS2 enabled. Static quality, unit/docs and all Python 3.11–3.13 BIND 9 integration CI checks passed at the documentation commit. No new configuration field or schema migration is required for DynDNS2. Actual VM upgrade was intentionally not performed; existing install remains unchanged. Issue #6 is closed. Remaining milestone work: Issue #7 release candidate and owner-approved prerelease.
