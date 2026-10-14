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
