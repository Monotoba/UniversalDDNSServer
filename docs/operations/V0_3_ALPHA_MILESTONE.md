# v0.3.0a1 — DynDNS2 compatibility and client usability

**Status:** Planned; not tagged or published. This milestone implements the Phase 2 usability work in the original [implementation plan](../IMPLEMENTATION_PLAN.md), rather than revisiting the completed v0.2 audit/recovery scope.

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

Implement Issue #4 first; do not perform another VM update until there's meaningful functional progress and automated tests are passing.
