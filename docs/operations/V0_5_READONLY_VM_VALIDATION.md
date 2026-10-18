# v0.5.0a1 read-only lab dashboard validation

**Status: smoke procedure executed on the user's upgraded disposable Ubuntu VM on 2026-10-17; partial acceptance only.** The smoke script itself does not upgrade, restart or modify any service; a separately authorized guarded upgrade preceded it.

## Preconditions and deployment gate

1. Independently confirm the guest is the intended **isolated** Ubuntu lab VM, the approved cold backup still exists, and that the VM has no production DNS connectivity.
2. Record the existing guest checkout SHA and deployed API version. If the guest is still on older code, **stop**: obtain separate authorization for the guarded upgrade, including a backup and rollback plan. Do not imply GitHub merges automatically update it.
3. Only after an explicitly authorized upgrade to a reviewed v0.5 candidate, verify that the API listens on `127.0.0.1:8765` and the services are active. Use a previously provisioned, currently scoped **read-only** bearer token with `intents:read` and a known allowed record ID. Never paste that token into chat, logs or shell arguments.

## Non-mutating smoke verification

From the actual upgraded VM's repository checkout, run:

```bash
bash deploy/verify-v0.5-dashboard-readonly.sh ALLOWED_RECORD_ID
```

The script prompts for the token invisibly and verifies loopback dashboard assets, HTTP 401 for unauthenticated record discovery, authenticated record discovery, the bounded recent-intent API response and authorized record details. It prints **only** operation statuses and the authoritative observation state, not the token, RRset addresses or full API responses. No PUT/POST/DELETE or DNS UPDATE is sent.

`unavailable` is an acceptable schema outcome but **does not pass** the separately required live authoritative DNS observation acceptance criterion. A controlled isolated BIND fixture and approved temporary DNS record are required for observed match/mismatch/absence testing. This read-only script cannot establish that updates never occurred elsewhere.

## October 17 lab evidence (user-reported)

- Guest `uddns-prealpha` upgraded with guarded updater from SHA `a15dadf8` (0.3.0a1) to SHA `8b909866` (0.5.0a1); update and installed-host verification reported PASS. API, worker and BIND active; API loopback liveness passed.
- Fresh cold backup `~/vm-backups/uddns-pre-v05-20261017T202744Z/` included QCOW2, seed ISO and VM XML; user confirmed both SHA-256 checks and clean `qemu-img check`. SQLite online snapshot integrity passed; updater snapshot `upgrade-backup-20261017T203243Z` retained. Neither rollback nor new backup boot recovery was tested.
- Read-only smoke on `home`: dashboard HTML/JS HTTP 200; unauthenticated records HTTP 401; authorized discovery/history/details schema/scope PASS, final read-only smoke PASS. Live authoritative observation `differs_from_template` confirmed independently: configured A 192.0.2.10 TTL 60, BIND authoritative A 192.0.2.42 TTL 60, NOERROR and AA.
- Issued read-only test bearer was disclosed in user-shared terminal output; it was then revoked by credential reference `cred-3`, confirmed by subsequent inventory. The original `vm-test` credential `cred-1` was also revoked; future credential-dependent tests need explicit replacement. No token is retained in this document.
- **Subsequent October 17–18 evidence:** Live `absent` confirmed using activated `v05-observation-test` template with authoritative NXDOMAIN; authorized discovery HTTP 200, unrelated `home` detail HTTP 404, read-only PUT HTTP 403. Credential `cred-4` revoked, token file deleted, fixture returned inactive at revision 3. Live `matches_template` confirmed for temporarily active `catalog-live-v04` (A 192.0.2.73 TTL 60 on both sides); credential `cred-5` revoked, token file deleted, fixture returned inactive at revision 5. Existing DNS RRsets were not deliberately updated.
- Isolated fixture failure tests against deployed source commit `8b909866` in a separate virtualenv on 2026-10-18: 6 passed, 3 subtests passed (`tests/test_record_detail_observation.py`, `tests/test_runtime_dns_observer.py`). Two nonfatal warnings concerned Starlette/httpx test-client deprecation and pytest cache permission in the root-owned repository. This is **not** live BIND failure evidence.
- Still untested: live DNS timeout/transport error `unavailable`, inactive-record visibility denial, independent no-write audit, further principal-isolation cases, complete network isolation (guest has a default route and SSH listens on all interfaces), rollback and restored application-level behavior.

## Evidence to record privately

Capture: exact guest ID, git revision, API version, snapshot identifier, service/listening checks, script exit status, observed status and relevant sanitized audit/BIND evidence. Retain the results outside GitHub if host-specific or sensitive; record only a high-level redacted conclusion in the release checklist.

## Unfinished gates

The script does **not** test remote-client rejection, hidden record IDs belonging to another principal, token revocation, write denial, authoritative DNS negative answers, UI rendering, database restore, guarded rollback or any production security assurance. Test these separately in the isolated guest after approval. Do not mark the overall VM gate complete merely because this smoke check passes.
