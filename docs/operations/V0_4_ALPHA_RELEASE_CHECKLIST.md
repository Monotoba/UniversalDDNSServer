# v0.4.0a1 experimental alpha release gate

**Status: not approved, not released.** This checklist is a planning and evidence record for a possible v0.4.0a1 prerelease. It does not supersede the historical v0.1/v0.3 release records, or authorize tagging and publication.

## 0. Candidate and repository state
- [ ] Confirm feature PRs merged and no unreviewed release blockers remain.
- [ ] Align `pyproject.toml` and FastAPI metadata with v0.4.0a1; never re-use a published tag.
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
- [ ] Run guarded `update-vm.sh` upgrade and read-only `--verify`; confirm API and worker startup and backup location.
- [ ] Run static record `vm-test.sh update` against isolated `home.lab.invalid` and verify authoritative BIND output.
- [ ] Run `vm-test.sh tsig-deny` against prohibited names.
- [ ] With an authorized **non-root** local operator, test catalog create, activate, issue, discover, submit, deactivate, blocker listing, revoke by reference, and safe reactivation against the isolated test zone (separate validation from the static VM update test).
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

- No complete verified installed-VM exercise of catalog lifecycle and operator-group credential administration has yet been recorded.
- Actual in-flight network interruption and strong DNS-write fencing remain unproven.
- Published v0.3.0a1 is the last documented release; development version metadata still reads `0.3.0a1`.
- No approval has been granted for a v0.4 release.

Evidence links and disposition should be added next to each checkbox before declaring the release ready.
