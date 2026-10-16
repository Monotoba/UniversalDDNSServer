# Implementation plan

Phases are engineering milestones, not release dates. Status reflects reviewed repository implementation and reported test evidence as of 2026-10-16. A checked item describes its specified scope, not production readiness. See [v0.4 alpha release gate](operations/V0_4_ALPHA_RELEASE_CHECKLIST.md) and [changelog](../CHANGELOG.md).

## Phase 0 — design and groundwork
- [x] Architecture proposal, ADR-0001 and ADR-0002.
- [x] Core RRset model, interfaces and SQLite desired-state persistence.
- [x] Authorization-gated intent orchestration and SQLite intent journal.
- [x] Initial unit tests and Python 3.11–3.13 CI.
- [ ] Generalized DNS RRset type design ADR and durable schema migration strategy beyond additive experimental migrations.

## Phase 1 — secure DNS publication (experimental scope)
- [x] Bind REST requests to validated bearer principals with scoped record access and persisted token hashes; local operator CLI additionally requires verified non-root POSIX identity.
- [x] Durable intent-state reconciliation against authoritative DNS with operator-readable inspection and bounded recovery paths.
- [x] Worker lifecycle and per-record leases with tests; general multi-writer correctness, crash recovery and in-flight DNS-write fencing remain unproven.
- [x] Persist per-principal request idempotency keys with conflicting-payload checks.
- [x] Backend retry classification and bounded scheduling; ambiguous external DNS writes still require observation/reconciliation rather than unconditional retry.
- [x] RFC 2136/TSIG adapter and isolated BIND 9 A/AAAA integration and rejection tests.
- [ ] Establish atomic cross-store/remote-DNS recovery semantics across all failures. SQLite state changes are durable but DNS publication is an external operation.
- [ ] Production HTTPS ingress, secure distributed rate limiting and internet-facing deployment hardening. The experimental FastAPI listener is loopback-only, with process-local rate limiting.

## Phase 2 — usability and operations (experimental scope)
- [x] Scoped DynDNS2-compatible update endpoint for statically configured records, with UDDNSUpdater interoperation; catalog-managed records are not exposed through DynDNS2.
- [x] Guarded Ubuntu VM installation/upgrade verification, SQLite backups, runbooks and isolated BIND 9 test deployment.
- [x] Experimental SQLite-backed A/AAAA record catalog, revision-controlled activation/deactivation and scoped REST discovery/update.
- [x] Authorized local-only record and credential administration, credential revocation, blocker inventory and SQLite audit events.
- [x] Disposable Ubuntu VM live catalog -> REST -> worker -> authoritative BIND A test passed on 2026-10-16; temporary credential revoked and test record deactivated.
- [x] Negative TSIG update authorization test passed on 2026-10-16: disallowed name refused and not created; original name-only BIND policy restored.
- [ ] Validate a demonstrably cold, restorable VM backup and exercise isolated restore/rollback. A QCOW2 copy passed SHA-256 and `qemu-img check`, but its shutdown completion before copying has not been established.
- [ ] Harden operator database access: test VM currently grants `universalddns-operators` write access to the service-state directory. Document and test a narrower operational permission model.
- [ ] Validate full production-safe upgrade, restoration, networking, monitoring and operational security. Current VM evidence is laboratory-only.

## Phase 3 — management
- [x] Initial local operator roles (POSIX group) and audited credential mutations; SQLite audit is not tamper-evident.
- [ ] Generalized roles/groups and delegated authorization.
- [ ] Browser management interface and secure remote administration API.

## Phase 4 — plugins
- [ ] Backend capability negotiation, provider adapters, versioned SDK and contract tests.

## Release tracking
- [x] v0.3.0a1 experimental prerelease documented and published.
- [x] v0.4.0a1 package/API version alignment, CI package-build inspection, and experimental VM catalog publication evidence recorded.
- [ ] v0.4.0a1 final release gate, owner publication approval, immutable tag and verified release assets. **Not published.**

Every functional change needs appropriate tests, docs and CI. Experimental test passes do not imply a production support claim.
