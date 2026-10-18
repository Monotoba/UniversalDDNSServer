# Implementation plan

Phases are engineering milestones, not release dates. Status reflects reviewed repository implementation and reported test evidence as of 2026-10-17 (repository state and user-reported lab VM evidence through 2026-10-17). A checked item describes its specified scope, not production readiness. See [v0.5 alpha candidate gate](operations/V0_5_ALPHA_RELEASE_CHECKLIST.md) and [historical v0.4 release gate](operations/V0_4_ALPHA_RELEASE_CHECKLIST.md) and [changelog](../CHANGELOG.md).

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
- [x] Capture a powered-off VM backup after explicitly observing `virsh domstate` = `shut off`; saved VM XML, QCOW2 disk and seed ISO in `~/vm-backups/uddns-prealpha-20261016-cold/`. User verified both SHA-256 checksums, clean `qemu-img check`, file inventory and subsequent VM restart (2026-10-16).
- [x] Boot an independent isolated restore VM from a copied cold QCOW2: Ubuntu 24.04 reached login, no network interfaces were attached, libguestfs recovered application files/systemd units, restored SQLite `PRAGMA integrity_check` returned `ok` with expected five tables, and QEMU guest agent confirmed API, worker and BIND services each `active` (2026-10-16).
- [ ] Validate application-level request/DNS behavior inside the restored guest and exercise a controlled rollback/failure recovery; basic boot, filesystem, DB and service activation are not a production disaster-recovery guarantee.
- [x] Audit lab operator ACLs and service listening boundary (2026-10-16): non-root operator group has SQLite file `rw-` and parent `rwx`, config read only, TSIG service-only, no world access; API binds `127.0.0.1:8765`; readiness and all three services passed.
- [ ] Harden direct operator database access for deployment beyond the disposable VM: current group write privileges allow bypass of application-level authorization and SQLite audit; design/test a privileged administrative broker or equivalent narrower model.
- [ ] Validate full production-safe upgrade, restoration, networking, monitoring and operational security. Current VM evidence is laboratory-only.

## Phase 3 — management
- [x] Initial local operator roles (POSIX group) and audited credential mutations; SQLite audit is not tamper-evident.
- [ ] Generalized roles/groups and delegated authorization.
- [x] Experimental **local-only read-only** browser dashboard on development `main` (PRs #164–#168): scoped record discovery/details, recent principal-owned intent history, SQL-side status/record filters, page-only counts, and authoritative DNS observation using the configured backend. Bearer `intents:read` remains required for data; dashboard assets require loopback transport. Subsequent VM upgrade and smoke verification were completed on 2026-10-17 (see v0.5 milestone below).
- [ ] Authorized record editing and credential administration in the browser; no mutation controls or remote management API are implemented.
- [ ] Secure remote administration API and production-grade browser authentication/session protections.
- [ ] **Superuser-only emergency recovery (Phase 3):** design and implement an explicit, root-authorized `universalddns recover-admin` CLI workflow for the future application superuser; ordinary users and delegated administrators must not invoke emergency recovery or reset the superuser through the UI. All other user credential resets require an appropriately authorized administrator, with auditable identity verification and immediate invalidation of superseded sessions/credentials.
- [ ] **Online recovery and remote operations:** normal superuser recovery should not restart the API, worker, or BIND and should not change DNS records; use the protected local administrative broker/credential store with atomic, single-use, short-lived recovery capability and no secret exposure in logs. Allow operation over authenticated SSH on an operator-configured **nonstandard port** (no port-22 assumption); prefer a private management network and SSH key authentication. SSH/VPN authorization is independent of application account recovery. Document a separate offline/disaster-recovery path for damaged databases or unavailable administrative services.
- [ ] **Recovery threat model and tests:** verify only root-authorized local/SSH operators can initiate superuser recovery; reject ordinary users and application admins, replayed/expired recovery credentials, unauthorized network requests and improper session persistence; audit without leaking secrets. Do not create an automatically triggered startup recovery file, environment-variable backdoor or public recovery endpoint.

## Phase 4 — plugins
- [ ] Backend capability negotiation, provider adapters, versioned SDK and contract tests.

## Release tracking
- [x] v0.3.0a1 experimental prerelease documented and published.
- [x] v0.4.0a1 package/API version alignment, CI package-build inspection, and experimental VM catalog publication evidence recorded.
- [x] v0.4.0a1 experimental prerelease approved and published 2026-10-16 from commit `592153ed920345d282cf55c4c7995d4d9fe0e4cb` with annotated tag, wheel, source distribution and published SHA-256 checksums. [Release](https://github.com/Monotoba/UniversalDDNSServer/releases/tag/v0.4.0a1).

Every functional change needs appropriate tests, docs and CI. Experimental test passes do not imply a production support claim.

## Post-v0.4.0a1 packaging maintenance

- [x] Migrate development-branch `pyproject.toml` from deprecated license table to PEP 639 SPDX `BSD-2-Clause` and explicit `LICENSE` inclusion, with setuptools build requirement `>=77`. This is a post-release change; the immutable v0.4.0a1 tag and its published artifacts are unchanged.
- [ ] Verify next development build metadata and LICENSE distribution on supported Python versions; no claim that already-published v0.4.0a1 packages include this change.

## v0.5.0a1 dashboard milestone — candidate, not released (2026-10-17)

- [x] PRs [#164](https://github.com/Monotoba/UniversalDDNSServer/pull/164), [#165](https://github.com/Monotoba/UniversalDDNSServer/pull/165), [#166](https://github.com/Monotoba/UniversalDDNSServer/pull/166), [#167](https://github.com/Monotoba/UniversalDDNSServer/pull/167) and [#168](https://github.com/Monotoba/UniversalDDNSServer/pull/168) merged after five-workflow exact-head gates including Python 3.11–3.13 matrix evidence.
- [x] Read-only dashboard uses existing scoped bearer authorization; displays only active authorized records and principal-owned recent intents. History is SQL-filtered before page limits, and summaries apply to the displayed page, not all updates.
- [x] Record-detail endpoint can query the configured authoritative RFC 2136 DNS backend **read-only**. Observation errors report `unavailable`; `matches_template` compares against a configured template and is not proof that a particular intent published successfully.
- [x] Align development candidate package and FastAPI versions to **0.5.0a1** and prepare draft release notes (release candidate PR; publication not approved). The immutable v0.4.0a1 release is unchanged.
- [x] Prepare non-mutating [v0.5 dashboard VM verification procedure](operations/V0_5_READONLY_VM_VALIDATION.md) and loopback-only smoke script. Procedure prepared in PR #171; it was subsequently executed on the upgraded guest on 2026-10-17.
- [x] On 2026-10-17, user confirmed guarded upgrade of disposable `uddns-prealpha` from `a15dadf81efd0f9013260974d386e642703b0175` (0.3.0a1) to `8b909866d9c68db3f97f9f6387e764774e9a9d79` (0.5.0a1); updater returned `FINAL_RESULT=PASS`, API/worker/BIND active and `/health/live` responded. Fresh powered-off QCOW2, seed ISO and VM XML saved in `~/vm-backups/uddns-pre-v05-20261017T202744Z/`, checksum checks passed and `qemu-img check` reported no errors; separate SQLite online backup integrity passed and updater retained `upgrade-backup-20261017T203243Z`. This is a lab upgrade, not rollback validation.
- [x] On 2026-10-17, read-only dashboard smoke check against `home` passed: dashboard HTML/JS HTTP 200, unauthenticated discovery HTTP 401, authorized record discovery/history/detail schemas and scope. Live DNS observation correctly returned `differs_from_template`: configured `home.lab.invalid` A 192.0.2.10 TTL 60 versus authoritative BIND A 192.0.2.42 TTL 60 (NOERROR, AA). The transient `intents:read` bearer credential was exposed in the shared terminal transcript and subsequently revoked (`cred-3`); older `vm-test` credential `cred-1` was also revoked, so later VM regression tests need an intentionally issued replacement credential.
- [x] On 2026-10-17–18, live VM observation returned `matches_template` for `catalog-live-v04` (configured and authoritative A 192.0.2.73, TTL 60), `differs_from_template` for `home`, and `absent` for temporary `v05-observation-test` (authoritative NXDOMAIN). Scoped read-only credential could discover its authorized fixture, received HTTP 404 for unauthorized `home` details, and HTTP 403 for a PUT attempt; no successful DNS write was requested. Temporary credentials `cred-4` and `cred-5` were revoked and token files deleted; both catalog test records returned to inactive (`v05-observation-test` revision 3, `catalog-live-v04` revision 5).
- [x] On 2026-10-18, isolated Ubuntu VM test venv executed `tests/test_record_detail_observation.py` and `tests/test_runtime_dns_observer.py`: 6 tests and 3 subtests passed, exercising observer failure handling without disrupting live BIND9. Two nonfatal warnings concerned Starlette's httpx deprecation and inability to create a pytest cache inside the root-owned source checkout.
- [x] On 2026-10-18, isolated TestClient API called the actual `RFC2136Backend.observe()` over TCP to an intentionally non-listening loopback port. Connection failure yielded HTTP 200 with `authoritative.status=unavailable`, not `absent`; `dashboard_dns_observation_failed` audit event was emitted. API/worker/BIND9 stayed active; `TRANSPORT_FAILURE_RESULT=PASS`. No production service was fault-injected.
- [ ] Complete **systemd-managed API** observer timeout/transport-error `unavailable`, separate inactive-record denial, independent no-DNS-write audit, and full test-VM security acceptance. A real TCP failure in an isolated TestClient is not a failure of the running managed service or production readiness.
- [ ] Review the dashboard/browser security boundary and API worker credential separation: current runtime constructs `RFC2136Backend(settings.dns)` in the API process and already loads TSIG credentials for other runtime operations. This milestone does not claim a dedicated least-privilege observer identity.
- [ ] Re-run the five workflows on an exact frozen release candidate SHA; inspect LICENSE and package metadata in both wheel and sdist and review release assets/checksums.
- [ ] Obtain explicit owner approval before tagging, publishing v0.5.0a1, or deploying to any VM.
- [ ] Validate the still-unfinished recovery, role delegation, privileged-broker isolation and internet-facing security work separately; v0.5 is **experimental** and not production-ready.

See [v0.5.0a1 release checklist](operations/V0_5_ALPHA_RELEASE_CHECKLIST.md) and [dashboard feature guide](features/LOCAL_READONLY_DASHBOARD.md).
