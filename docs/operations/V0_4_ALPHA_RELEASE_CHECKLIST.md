# v0.4.0a1 experimental alpha release gate

**Status: published experimental prerelease (2026-10-16).** This checklist records the approval, verification and evidence for v0.4.0a1. It does not establish production readiness.

## 0. Candidate and repository state
- [ ] Confirm feature PRs merged and no unreviewed release blockers remain.
- [x] Align `pyproject.toml` and FastAPI metadata with `0.4.0a1` on `main`; release tag not created.
- [ ] Review `CHANGELOG.md`, [draft release notes](../releases/v0.4.0a1-draft.md), README and operator/API guides.
- [ ] Freeze a candidate commit SHA and independently review its diff and dependencies.

## 1. Automated quality gate (final candidate SHA only)
- [x] Static quality workflow passed for candidate `8f04de1c` ([Actions run](https://github.com/Monotoba/UniversalDDNSServer/actions/runs/38878895278)); must rerun after candidate changes.
- [x] Unit and documentation tests passed for `8f04de1c` ([Actions run](https://github.com/Monotoba/UniversalDDNSServer/actions/runs/38878895293)); rerun after changes.
- [x] Integration matrix passed for `8f04de1c` ([Actions run](https://github.com/Monotoba/UniversalDDNSServer/actions/runs/38878895286)); rerun after changes.
- [x] CI built and inspected wheel/sdist for `8f04de1c` ([Actions run](https://github.com/Monotoba/UniversalDDNSServer/actions/runs/38878895445)); checked version, selected package contents, license and sensitive path patterns. More thorough manual artifact review and final tagged rebuild remain pending.
- [x] Record five workflow runs for `8f04de1c`, including [operator CLI](https://github.com/Monotoba/UniversalDDNSServer/actions/runs/38878895284), all successful. **These must be refreshed for any final candidate SHA after this documentation update.**

## 2. Disposable Ubuntu VM validation
- [x] Preserve an independent **powered-off disk backup** and protected SQLite upgrade backup; user confirmed shutdown loop waited for `shut off`, copied VM XML/QCOW2/seed ISO to `~/vm-backups/uddns-prealpha-20261016-cold/`, verified both SHA-256 checksums and `qemu-img check`, then restarted the VM (2026-10-16). Guest checkout was `a15dadf8` during VM tests; the separate restored copy subsequently booted and passed service checks.
- [ ] On actual `uddns-prealpha` guest, validate hostname, isolation, active default libvirt network and loopback API binding.
- [x] Run guarded `update-vm.sh` upgrade and read-only `--verify`; user-provided output confirmed API/worker/named active at `a15dadf8` with backup `/var/lib/universalddns/upgrade-backup-20261016T085637Z`.
- [x] Run static record `vm-test.sh update` against isolated `home.lab.invalid` and verify authoritative BIND output; user-provided output 2026-10-16: PASS (earlier deployed revision).
- [x] Run `vm-test.sh tsig-deny` against prohibited names; user-provided output on `uddns-prealpha` 2026-10-16: `PASS: BIND rejected unauthorized TSIG update with REFUSED; no record created`; `FINAL_RESULT=PASS`; log `/home/ubuntu/uddns-results/20261016T092020Z-tsig-deny.log`.
- [x] With authorized non-root Ubuntu operator, test isolated CLI create/activate/issue/block/revoke/reactivate/audit and live installed-service catalog create/activate/issue/discover/submit/publish/deactivate/revoke. User-provided logs 2026-10-16: PASS; live name `catalog-live.lab.invalid.` published `192.0.2.73` on `a15dadf8`. Safe reactivation verified in separate isolated CLI fixture, not live service.
- [ ] Confirm no stale token grants unrelated-record access, no accidental reactivation grant, and queued work is rejected after authorization loss; recognize in-flight write limitations.
- [ ] Inspect local credential history; confirm verified operator identity, no bearer/digest disclosure and durable audit after restart.
- [x] Verify isolated cold-backup boot and core recovered state: separate `uddns-restore-test` without NIC booted Ubuntu 24.04, offline libguestfs found application/units/SQLite, SQLite `integrity_check` returned `ok`, and QEMU guest agent returned exit code 0 with API, worker and named all `active` (2026-10-16).
- [ ] Exercise a controlled rollback/failure scenario and restored application-level API/DNS behavior; service activation alone is insufficient.

## 3. Security and operational review
- [x] Review lab OS group and ACLs (user-provided read-only audit 2026-10-16): `ubuntu` belongs to `universalddns-operators`; state directory group ACL `rwx`, database ACL `rw-`, config ACL `r--`, TSIG account-only, no world access. **Known limitation:** directory/database write privileges permit direct SQLite changes outside application authorization/audit.
- [ ] Verify credential CLI refuses root, changed UID and unauthorized users.
- [x] Verify restored BIND policy authorizes only `home.lab.invalid.` A after live validation; user's 2026-10-16 command output showed `named` active and both DNS records still resolving.
- [ ] Review credential `cred-N` reference stability caveat and SQLite audit tamper limitations.
- [ ] Review HTTP management exposure, external listeners and retry semantics in code. Installed VM socket check confirms Uvicorn bound only to `127.0.0.1:8765`, but this does not alone establish broader code/production behavior.
- [ ] Confirm security boundary caveats and outstanding limitations are retained in release notes.

## 4. Publication gate
- [x] Owner approved v0.4.0a1 and explicitly authorized publication of `592153ed920345d282cf55c4c7995d4d9fe0e4cb`.
- [x] Created annotated `v0.4.0a1` tag targeting exactly `592153ed920345d282cf55c4c7995d4d9fe0e4cb`; built wheel and sdist from detached approved checkout.
- [x] Local `sha256sum -c SHA256SUMS` passed; GitHub's uploaded asset digests match the published wheel, sdist and checksum file (see publication evidence below).
- [x] Published [v0.4.0a1](https://github.com/Monotoba/UniversalDDNSServer/releases/tag/v0.4.0a1) as a GitHub **prerelease**, with experimental limitations and three assets.
- [x] Independently verified GitHub release is not draft, `prerelease=true`, all three uploaded assets have expected SHA-256 digests, and annotated tag points to approved SHA.
- [ ] Provide host-specific local checkout / disposable VM update commands only after publication is confirmed.

## Known blockers/limitations

- Operator-group CLI fixture and live catalog-to-BIND tests **passed on the disposable VM** on 2026-10-16 using commit `a15dadf8`; live test left an inactive catalog fixture and DNS RRset. Reboot, full crash recovery and rollback still need review as independently scoped gates; negative TSIG-policy test passed on 2026-10-16.
- Actual in-flight network interruption and strong DNS-write fencing remain unproven.
- v0.4.0a1 was published on 2026-10-16; `main` package metadata reads `0.4.0a1`.
- Owner approval and separate publication authorization were obtained for the experimental v0.4.0a1 prerelease, not production deployment.

Evidence links and disposition should be added next to each checkbox before declaring the release ready.

## 2026-10-16 user-provided VM evidence

- The `uddns-prealpha` test VM upgraded and verified successfully at `a15dadf8`; API, worker and named services were active, API loopback checks passed, and a SQLite upgrade backup was retained.
- The verified `ubuntu` account belongs to `universalddns-operators`. Following PR #40, read-only operator preflight passed with TSIG file restricted to the service account.
- Isolated operator CLI lifecycle completed `PASS: isolated operator CLI issue, block, revoke, reactivate and audit`.
- BIND policy was explicitly extended for only `catalog-live.lab.invalid.` A; pretest authoritative NXDOMAIN confirmed.
- Live installed test reported `PASS: active catalog -> scoped REST -> worker -> authoritative BIND A`, followed by confirmed deactivation and temporary credential revocation. It left an inactive catalog row and published DNS RRset by design.
- **Unverified:** restored application-level request/DNS behavior and controlled rollback, ACL rollback/production permission hardening, final candidate checks after documentation edits and release-asset verification. Operator confirmed BIND catalog-only grant removal with `named-checkconf -z`, reload and readback; both `home` and `catalog-live` DNS records still resolved.

## 2026-10-16 candidate CI artifact evidence

- Commit `8f04de1cb1393c89bfc164f1ee47d5077f1d8eef` passed [static quality](https://github.com/Monotoba/UniversalDDNSServer/actions/runs/38878895278), [unit/docs](https://github.com/Monotoba/UniversalDDNSServer/actions/runs/38878895293), [operator CLI](https://github.com/Monotoba/UniversalDDNSServer/actions/runs/38878895284), [BIND integration](https://github.com/Monotoba/UniversalDDNSServer/actions/runs/38878895286), and [package inspection](https://github.com/Monotoba/UniversalDDNSServer/actions/runs/38878895445).
- Wheel: `universalddnsserver-0.4.0a1-py3-none-any.whl`, SHA-256 `81895cba827f93ab3f8df2e420ca105ffb642c4d2c1fb71921d4c1ce5647f20b`.
- Sdist: `universalddnsserver-0.4.0a1.tar.gz`, SHA-256 `183d84ae8d51007b37b14c38f6bcdce7bb11613f7d9eec1d788cc87b0d1f9e11`.
- Digests are from the successful **CI build**, not downloaded/published release assets. Do not claim artifact portability, reproducibility, or release verification from these values. Rebuild and verify final assets from the approved immutable tag.

## 2026-10-16 negative TSIG authorization evidence

- After restoring BIND's original named-only update policy, the operator executed `vm-test.sh tsig-deny` on `uddns-prealpha`.
- The attempt to update `disallowed-tsig-probe.lab.invalid.` with the valid lab TSIG credential was rejected with `REFUSED`; the probe did not create an A record. Test exit reported `FINAL_RESULT=PASS`, with guest log `/home/ubuntu/uddns-results/20261016T092020Z-tsig-deny.log`.
- Evidence is user-provided CLI output. No secret material was included. This verifies the restricted policy for the tested name, not every possible DNS ACL or production deployment.

## 2026-10-16 verified cold VM disk backup

- After an explicit shutdown-state polling loop completed, the operator copied `/var/lib/libvirt/images/uddns-prealpha.qcow2`, `uddns-prealpha-seed.iso` and the inactive libvirt domain XML to `~/vm-backups/uddns-prealpha-20261016-cold/`.
- User-provided inventory: QCOW2 ~3.9 GiB, seed ISO ~366 KiB, XML ~6.5 KiB, SHA256SUMS file present. Both `sha256sum -c SHA256SUMS` entries returned `OK`; `qemu-img check` reported no errors. Guest was started and subsequently reported `running`.
- This verifies a cold file-level recovery copy and its structural/checksum integrity. An independent isolated restore subsequently booted and passed offline SQLite and service-active checks (below); full application-level recovery and production disaster recovery are not yet established.

## 2026-10-16 isolated VM restoration evidence

- User copied the cold backup to separate disk `/var/lib/libvirt/images/uddns-restore-test.qcow2` and defined `uddns-restore-test` with no network interfaces; original guest was unaffected. Restore booted to Ubuntu 24.04.5 serial login prompt.
- Following guest shutdown, `virt-inspector` identified Ubuntu 24.04; read-only `virt-ls` confirmed `/opt/universalddns/{src,venv}`, `/var/lib/universalddns/state.sqlite3`, upgrade backup folders, `universalddns-api.service` and `universalddns-worker.service`.
- Restored SQLite database copy passed `PRAGMA integrity_check` (`ok`), with tables `api_tokens`, `credential_audit`, `managed_records`, `sqlite_sequence`, `update_intents`. No bearer-token contents were disclosed.
- QEMU guest-agent channel on the booted restored VM returned successful `guest-ping`; `systemctl is-active universalddns-api universalddns-worker named` exited 0 and decoded to `active`, `active`, `active` (guest process PIDs 887 and 894). Network interface list remained empty.
- These checks demonstrate isolated boot and basic application state/service recovery, not exercised HTTP requests, BIND DNS queries after restore, in-flight failure handling, or production recovery SLAs.

## 2026-10-16 operator ACL and listener evidence

- Installed `uddns-prealpha` reported non-root `ubuntu` UID 1000 in group `universalddns-operators` (GID 987), dedicated non-login service user `universalddns` UID 999.
- `/var/lib/universalddns`: named operator group ACL `rwx`, `other::---`; `state.sqlite3`: named operator group `rw-`, `other::---`.
- `/etc/universalddns`: operator traverse-only `--x`; `config.json`: operator `r--`; `tsig.json`: service owner `rw-`, no operator ACL, group/other `---`.
- Uvicorn listened on `127.0.0.1:8765` only in captured socket output; operator read-only readiness passed and API, worker, named each reported `active`.
- **Residual trust boundary:** SQLite directory and database write grants allow trusted local operators to bypass application-enforced authorization and tamper with local audit data. Do not advertise this as hardened multi-tenant administration; no permissions were modified in this review.

## 2026-10-16 publication verification

- Approved immutable source commit: `592153ed920345d282cf55c4c7995d4d9fe0e4cb`. All five `main` workflows passed at that SHA. Annotated tag `v0.4.0a1` points to it.
- User built the wheel/sdist locally from a detached checkout of the approved SHA; package metadata passed, and `sha256sum -c SHA256SUMS` returned `OK` for each.
- [GitHub prerelease](https://github.com/Monotoba/UniversalDDNSServer/releases/tag/v0.4.0a1) independently confirmed `prerelease=true`, `draft=false`, with all assets `uploaded`.
- Published wheel SHA-256: `7ae25bd312f61617d29a37ebe9c5c1d41e14474a63cbe681591e675f8082a055`.
- Published sdist SHA-256: `ecedf2127a72b39975f21178dc52d4a5d70fdbbdfb5d0a147a1554c47dae99c3`.
- Published `SHA256SUMS` asset SHA-256: `cb40244ec4de19c43e9144ddc6d3a5fee251f67cfcbe2ce2c19ac1cd97a5935b`.
- Build emitted setuptools' `project.license` TOML-table deprecation warning; defer SPDX metadata migration to the next development cycle. Production-grade SQLite trust isolation and in-flight fencing remain unresolved.
