# Ubuntu VM deployment evidence — 2026-10-14 UTC

Source: user-operated `uddns-prealpha` VM and archived diagnostic file `uddns-validation-20261014T022433Z.tar.gz`. The archive is **not committed** because host logs can include sensitive data.

## Environment
- Ubuntu Server 24.04.5 LTS, kernel 6.8.0-142-generic, Python 3.12.3.
- BIND 9 package 9.18.39-0ubuntu0.24.04.7.
- Separate `universalddns-api.service`, `universalddns-worker.service`, and `named.service`, all enabled and active.

## Observed PASS evidence
- Installer reports success; local service-account configuration, credential and SQLite access checks passed.
- API liveness returned success; unauthenticated intent access rejected.
- Listener observed only on `127.0.0.1:8765`.
- `20261014T021823Z-update.log`: scoped real localhost API accepted intent, publishing worker applied it, and authoritative BIND A record matched.
- `20261014T022342Z-verify.log`: checks passed after reboot.
- Journal records shutdown at 02:23:23 UTC, new boot marker `ecac6a67b57b46ce836c40aaae475268`, and startup of both UniversalDDNS units at 02:23:32 UTC.
- No obvious app tracebacks or permissions errors found in collected logs.

## Not established
- SQLite backup *and restore* with intent integrity.
- Interrupted pending or applying intent recovery on this installed host, including no duplicate publication.
- Detailed TSIG privilege / firewall and secrets review.
- Repeated complete end-to-end publication *after reboot* (post-reboot checks covered services and authentication).
- Version alignment, signed/reviewed release artifacts.

Do not claim those checks passed. Release remains blocked pending review.

## Follow-up evidence: archive 20261014T123547Z

User-operated `uddns-validation-20261014T123547Z.tar.gz` reviewed; raw archive retained outside Git.

- SQLite scratch backup/restore: **PASS**, twice (`024616Z` and `024730Z`), with JSON exit_code 0. All table data matched the live database; installed database was not overwritten.
- Worker pending-intent restart: **PASS**, twice at those same timestamps, with JSON exit_code 0. Request replay preserved the intent ID, worker restart applied the pending update, and BIND authoritative DNS matched.
- Service status in newest archive: `universalddns-api`, `universalddns-worker`, and `named` were enabled and active. The API remained bound to `127.0.0.1:8765`.
- Collected journal contains no obvious application exceptions or permission denials. The keyword “disable” in BIND build flags is not a service failure.

### Evidence limits
The restore was into a scratch database, not an offline cutover of the installed database. The worker was stopped **before** enqueueing, so an actual in-flight DNS operation was not interrupted. The JSON result files record PASS and exit code, but not independent request counts at the DNS transport layer. The report script's own `report.log` can be empty because it archives before its exit trap writes the final result.

## Follow-up evidence: archive 20261014T125627Z

Uploaded VM archive reviewed on 2026-10-14. `20261014T125601Z-inflight.log` and companion `.json` show PASS/exit_code 0 for deterministic lost-acknowledgement recovery. This uses disposable SQLite and a simulated backend; no actual in-flight SIGKILL or real RFC 2136 transport fault was injected. `20261014T125613Z-verify.log.json` reports PASS/exit_code 0. `20261014T125625Z-report.log` and `.json` now include the report's own final PASS/exit_code 0 within the archive; the archiving omission is corrected. Existing scratch restore and pending-worker restart PASS records remain present. Offline installed-database cutover and live transport fault injection remain outstanding.

## Offline database cutover: archive 20261014T130728Z

The uploaded `uddns-validation-20261014T130728Z.tar.gz` contains `20261014T130716Z-offline-restore.log` and its machine-readable JSON result (`PASS`, exit code 0). Both application services were stopped for an offline database snapshot restoration. The test confirmed snapshot contents, `universalddns:universalddns` ownership and mode `0600`, then restarted API and worker. The nested installed-host verification reported all API, worker and BIND services active, SQLite and credential access valid, API liveness passed and anonymous intent access denied. Report generation itself recorded `PASS` within the archive. This restored a known-good snapshot, not a disaster-recovery exercise involving lost/corrupt state, and no update was in flight during the cutover.
