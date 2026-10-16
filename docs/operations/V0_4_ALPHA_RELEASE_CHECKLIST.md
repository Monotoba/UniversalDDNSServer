# v0.4.0a1 experimental alpha release gate

**Status: not approved, not released.** This checklist is a planning and evidence record for a possible v0.4.0a1 prerelease. It does not supersede the historical v0.1/v0.3 release records, or authorize tagging and publication.

## 0. Candidate and repository state
- [ ] Confirm feature PRs merged and no unreviewed release blockers remain.
- [x] Align `pyproject.toml` and FastAPI metadata with v0.4.0a1 in the candidate branch; verify the final merged SHA before tagging.
- [ ] Review `CHANGELOG.md`, [draft release notes](../releases/v0.4.0a1-draft.md), README and operator/API guides.
- [ ] Freeze a candidate commit SHA and independently review its diff and dependencies.

## 1. Automated quality gate (final candidate SHA only)
- [ ] Static quality workflow passes (Ruff, scoped mypy).
- [ ] Unit and documentation tests pass on Python 3.11, 3.12 and 3.13.
- [ ] Integration matrix passes using isolated BIND 9, SQLite, REST API and worker on Python 3.11–3.13.
- [ ] Build and inspect source distribution/wheel metadata and contents; confirm version, license and no credentials or runtime DB files.
- [ ] Record evidence URLs and SHA for **the same candidate commit**, not just preceding development PRs.

## 2. Disposable Ubuntu VM validation
- [ ] Preserve an independent powered-off VM disk backup/snapshot, plus protected SQLite backup; record VM disk and checkout revisions.
- [ ] On actual `uddns-prealpha` guest, validate hostname, isolation, active default libvirt network and loopback API binding.
- [x] Run guarded `update-vm.sh` upgrade and read-only `--verify`; user-provided output confirmed API/worker/named active at `a15dadf8` with backup `/var/lib/universalddns/upgrade-backup-20261016T085637Z`.
- [x] Run static record `vm-test.sh update` against isolated `home.lab.invalid` and verify authoritative BIND output; user-provided output 2026-10-16: PASS (earlier deployed revision).
- [ ] Run `vm-test.sh tsig-deny` against prohibited names.
- [x] With authorized non-root Ubuntu operator, test isolated CLI create/activate/issue/block/revoke/reactivate/audit and live installed-service catalog create/activate/issue/discover/submit/publish/deactivate/revoke. User-provided logs 2026-10-16: PASS; live name `catalog-live.lab.invalid.` published `192.0.2.73` on `a15dadf8`. Safe reactivation verified in separate isolated CLI fixture, not live service.
- [ ] Confirm no stale token grants unrelated-record access, no accidental reactivation grant, and queued work is rejected after authorization loss; recognize in-flight write limitations.
- [ ] Inspect local credential history; confirm verified operator identity, no bearer/digest disclosure and durable audit after restart.
- [ ] Preserve sanitized validation output; test rollback/restore in disposable snapshot only when explicitly planned.

## 3. Security and operational review
- [ ] Review OS group and filesystem ACL permissions for configuration, TSIG secret and writable SQLite directory; do not grant world access.
- [ ] Verify credential CLI refuses root, changed UID and unauthorized users.
- [ ] Verify intended BIND TSIG update policy for every activated test RRset.
- [ ] Review credential `cred-N` reference stability caveat and SQLite audit tamper limitations.
- [ ] Check that no external listener, public token management, production TLS claim, or automatic ambiguous write retry was added.
- [ ] Confirm security boundary caveats and outstanding limitations are retained in release notes.

## 4. Publication gate
- [ ] Explicit owner approval of release scope and final SHA.
- [ ] Create immutable `v0.4.0a1` tag only after approval; build artifacts from tagged source.
- [ ] Generate and independently verify `SHA256SUMS` for final wheel and sdist.
- [ ] Publish GitHub release as **prerelease**, with tested SHA, artifact checksums, migrations and limitations.
- [ ] Verify published tag, assets and release notes after publication.
- [ ] Provide host-specific local checkout / disposable VM update commands only after publication is confirmed.

## Known blockers/limitations

- Operator-group CLI fixture and live catalog-to-BIND tests **passed on the disposable VM** on 2026-10-16 using commit `a15dadf8`; live test left an inactive catalog fixture and DNS RRset. Reboot, negative TSIG policy, full crash recovery and rollback still need review as independently scoped gates.
- Actual in-flight network interruption and strong DNS-write fencing remain unproven.
- Published v0.3.0a1 remains the last documented release; candidate-branch version metadata is being moved to `0.4.0a1`, not yet tagged.
- No approval has been granted for a v0.4 release.

Evidence links and disposition should be added next to each checkbox before declaring the release ready.

## 2026-10-16 user-provided VM evidence

- The `uddns-prealpha` test VM upgraded and verified successfully at `a15dadf8`; API, worker and named services were active, API loopback checks passed, and a SQLite upgrade backup was retained.
- The verified `ubuntu` account belongs to `universalddns-operators`. Following PR #40, read-only operator preflight passed with TSIG file restricted to the service account.
- Isolated operator CLI lifecycle completed `PASS: isolated operator CLI issue, block, revoke, reactivate and audit`.
- BIND policy was explicitly extended for only `catalog-live.lab.invalid.` A; pretest authoritative NXDOMAIN confirmed.
- Live installed test reported `PASS: active catalog -> scoped REST -> worker -> authoritative BIND A`, followed by confirmed deactivation and temporary credential revocation. It left an inactive catalog row and published DNS RRset by design.
- **Unverified:** independent powered-off VM snapshot evidence, explicit negative TSIG-policy test, later removal of the catalog-only policy grant, ACL rollback/production permission hardening, final candidate tests and artifact inspection. These items remain unchecked until evidenced.
