# v0.1.0a1 pre-alpha release gate (not yet approved)

This is a candidate release checklist, **not** evidence that a release exists.

## Automated checks
- [x] Unit and documentation tests across Python 3.11, 3.12, 3.13.
- [x] Ruff and scoped mypy checks.
- [x] Isolated BIND 9, SQLite, RFC 2136/TSIG integration across Python 3.11–3.13.
- [x] UDDNSUpdater interoperability over a real localhost HTTP API and separate worker process in CI.
- [x] Parse systemd units and validate deployment shell script syntax in CI.

## Required manual validation on clean Ubuntu host
- [x] Install into documented /opt, /etc and /var/lib locations using a dedicated account (Ubuntu VM; see [evidence](VM_VALIDATION_2026-10-14.md)).
- [x] Validate service-account credential access and writable SQLite state, with API bound to loopback (full TSIG policy review remains open).
- [x] Start both real systemd units; run `deploy/validate-install.sh` and review sanitized results.
- [x] Confirm the API listens only on 127.0.0.1:8765, worker processes an update using a disposable DNS zone, and authoritative DNS is correct.
- [x] Stop the worker, queue an intent, verify replay preserves its intent ID, restart the worker, and verify authoritative DNS (twice on Ubuntu VM; pending-state test only).
- [ ] Test an actual interruption during in-flight DNS publication and verify reconciliation without unintended republishing; independently verify API service restart behavior.
- [x] Reboot the VM and confirm enabled services recover correctly (journal contains new boot marker).
- [x] Perform a SQLite online backup and scratch-database restore, verify integrity and compare all tables (twice on Ubuntu VM; live database left intact).
- [ ] Verify a full offline restoration procedure, restored file ownership/permissions and service startup against restored state.
- [ ] Review TSIG update policy scope, firewall, error logging and retention, secret handling, and open security limitations.
- [ ] Review resulting changes, version/tag and actual release artifacts before publishing.

## Release scope and known limitations
The pre-alpha is an experimental, loopback-only authenticated management API with a separate publishing worker. It is **not** an authoritative nameserver: an independently configured RFC 2136-capable DNS server is required. No production HTTPS termination, distributed rate limiting, general RRset compare-and-swap, unattended ambiguous-error retry strategy, or production deployment certification exists. Public DNS propagation and CGNAT/NAT reachability are not guaranteed. A successful HTTP 202 means *queued*, not *published*.

## Publish gate
Do not tag or publish `v0.1.0a1` until the manual checklist is evidenced and the packaging version agrees with the release tag. No GitHub release has been created at the time of this document.
