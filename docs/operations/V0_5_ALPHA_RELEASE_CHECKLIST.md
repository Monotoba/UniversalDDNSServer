# v0.5.0a1 experimental dashboard milestone — candidate gate

**Status: planning / not published (2026-10-17).** This is a new milestone,
not a retroactive change to the published [v0.4.0a1](https://github.com/Monotoba/UniversalDDNSServer/releases/tag/v0.4.0a1)
release. Do not interpret checked development items as release approval.

## Candidate definition
- [x] Merge dashboard foundation, recent history, filtering, per-record details, and read-only authoritative observation (PRs #164–#168).
- [ ] Independently review feature diff, dependencies, README, implementation plan, feature guides, and release notes.
- [x] Align `pyproject.toml` and FastAPI metadata to 0.5.0a1 in candidate PR; final merge and release approval remain separate gates.
- [ ] Freeze exact candidate commit and tag target. No tag or release is authorized yet.

## Automated candidate verification
- [ ] Pass static quality, unit and documentation tests, BIND/SQLite integration (Python 3.11, 3.12, 3.13), operator fixture and release candidate packaging **at the frozen candidate SHA**.
- [ ] Inspect new dashboard tests in each Python matrix log, including unauthorized record rejection, no DNS write, backend-failure `unavailable`, bounded filtering and runtime observer hookup.
- [ ] Verify wheel and sdist metadata, license inclusion (PEP 639), included modules, secret exclusion and SHA-256 values from the actual frozen candidate build.
- [ ] Document any differences between the reviewed code SHA, packaged artifact hashes and final immutable tag.

## Disposable VM verification (partial user-reported execution on 2026-10-17)
- [x] Prepare [read-only dashboard VM smoke procedure](V0_5_READONLY_VM_VALIDATION.md) and `deploy/verify-v0.5-dashboard-readonly.sh` without modifying a guest; **preparation is not execution**.
- [ ] Verify guest identity, **network isolation**, approved backup, and clean lab baseline. Guest identity, clean pre-upgrade tree, backups and loopback API/BIND listeners passed; full isolation is unproven because the guest has a default route and SSH listens on all interfaces.
- [x] With owner authorization, guarded VM upgrade passed from `a15dadf81efd0f9013260974d386e642703b0175` (0.3.0a1) to `8b909866d9c68db3f97f9f6387e764774e9a9d79` (0.5.0a1), `FINAL_RESULT=PASS`. Fresh October 17 powered-off backup at `~/vm-backups/uddns-pre-v05-20261017T202744Z/` passed SHA-256 and QCOW2 checks; pre-upgrade SQLite snapshot passed integrity; updater retained `/var/lib/universalddns/upgrade-backup-20261017T203243Z`. API, worker and named active after upgrade.
- [x] On October 17, dashboard HTML and JS HTTP 200, unauthenticated records HTTP 401, authorized `home` discovery/history/details and schema checks passed using `intents:read` only. The temporary token was subsequently revoked (`cred-3`); the unrelated pre-existing `vm-test` token (`cred-1`) was inadvertently revoked too and must be replaced before tests requiring it.
- [ ] Complete isolated BIND observation matrix: live **mismatch** passed on October 17 (`home.lab.invalid` desired 192.0.2.10 vs authoritative 192.0.2.42, both TTL 60, AA/NOERROR); `matches_template`, `absent`, and live error/timeout `unavailable` still untested. No DNS changes were made during read-only smoke test.
- [ ] Verify inactive and unauthorized record IDs are hidden, writes are not possible with read-only token, and no unintended DNS writes occur.
- [ ] Exercise a guarded rollback and verify restored application-level behavior; mere service activation is not disaster-recovery proof.

## Security and release authorization
- [ ] Reassess loopback/browser-origin assumptions, privileged operator broker, SQLite direct write permissions, token lifetime in browser memory and TSIG credential exposure in API runtime.
- [ ] Confirm no public HTTPS, delegated RBAC, distributed rate limiting, or production security claim is made.
- [x] Prepare [draft release notes](../releases/v0.5.0a1-draft.md) and align implementation plan/changelog in candidate PR.
- [ ] Independently review notes, plan and changelog; obtain explicit approval for tag/artifact publication.
- [ ] Independently verify GitHub prerelease state, tag SHA, assets and SHA-256 checksums **after** publication, if approved.

## Current evidence and limitations
- PRs #164–#168 were squash-merged after their five exact-head workflow checks passed; tests exercised on Python 3.11–3.13.
- The local dashboard cannot edit records or administer credentials. `GET /api/v1/intents` lists only the authenticated principal's currently visible record updates, and counts describe at most the displayed 20 results.
- The API runtime wires read-only RFC 2136 observation to record details; the October 17 installed-VM smoke test passed at candidate SHA `8b909866`, including a corroborated live `differs_from_template` result. This is partial validation only. DNS result labels refer to template equality, not a specific intent's success.
- The last published release remains v0.4.0a1. Candidate branch package/API metadata declare 0.5.0a1; there is no v0.5 tag or release.
