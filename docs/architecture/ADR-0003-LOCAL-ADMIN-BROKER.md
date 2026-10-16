# ADR-0003 — Privileged local administration broker (proposed)

**Status:** Proposed. Ping-only broker tested on a separate disposable VM, not deployed to the original lab VMs or production. No replacement CLI or SQLite ACL migration is deployed. See the observed-evidence log in `docs/testing/OPERATOR-BROKER-DISPOSABLE-VM.md`.

## Problem

The experimental local operator CLI needs `rwx` on the SQLite parent and `rw-` on the state database. This means authorized human users can edit credentials, records and audit entries outside the CLI, bypassing its validation.

## Decision direction

Introduce a minimal single-host administration broker running under a dedicated, non-login identity with access to the SQLite state, not the TSIG secret. Use a Unix-domain socket under a root-managed runtime directory. Its clients need only permission to connect; human users should lose direct database write permission **after** a separately tested migration.

Authenticate connecting clients from kernel `SO_PEERCRED` on Linux, then check the numeric UID against the local `universalddns-operators` group. Reject UID 0 and invalid/unrecognized peer identities. Do not trust any username, UID, or role supplied by request JSON. The `operator_peer` helper provides kernel-backed authentication; `operator_protocol` and `operator_broker` now provide a single bounded, versioned **ping-only** handler accepting no mutations. A socket-activated listener and sample systemd socket/service unit have been exercised on a **dedicated disposable VM**; no production admin operations are implemented. The implementation is not a hardened broker.

## Required gates before enabling

1. Design systemd ownership, directory traversal and socket mode (e.g. `0660`), socket activation and lifecycle; reject socket symlinks and unintended endpoints.
2. Apply hard request-size and response-size limits, timeouts, one documented protocol version, allowlisted operations and strict validation.
3. Explicitly restrict broker methods to catalog/credential management. Never expose arbitrary SQL, filesystem paths, DNS publishing credentials or unauthenticated token disclosure.
4. Preserve genuine kernel peer attribution in durable audit; define read-only operations, issuance secret output semantics, failure reporting and logging redaction.
5. Test root/unauthorized-user rejection, concurrent requests, restarts, upgrade/rollback and non-broker clients. Evaluate stale group membership, account revocation and PID/UID namespace constraints. Membership in the system group is a policy input, not a replacement for runtime access control.
6. Provision a separate test VM and verify operator CLI migration before **removing** existing SQLite directory/file ACLs. No automatic production ACL change or silently activated daemon.

## Compatibility

Until the above gates pass, retain the existing direct CLI unchanged for experimental installations. The published `v0.4.0a1` tag and assets are immutable and unaffected. The helper is Linux-specific; reject unsupported platforms rather than trust unverified identity.

## Residual risks

The broker's service identity can still modify SQLite audit history. Database-local audit is not tamper-evident. Full process compromise, in-flight DNS write fencing, delegated group authorization and production hardening are out of scope.

## Experimental systemd units (disposable VM only)

- `deploy/systemd/universalddns-operator.socket` provides a local `/run/universalddns/operator.sock` stream with mode `0660` and expected operator-group ownership; `deploy/systemd/universalddns-operator.service` runs a dedicated non-login account, initially only handling authenticated `ping` requests.
- The process accepts **only** one inherited systemd socket descriptor, validates the socket family/type/listening state and allowed filesystem namespace, and never creates a listening TCP endpoint or touches SQLite.
- These are experimental source units, enabled only on the dedicated disposable guest; this is not an endorsement for a production deployment. Before VM testing, verify the `/run/universalddns` parent directory is traversable by authorized operators but not writable by them, and that symlinks, socket replacements, unexpected socket paths, service privilege, and unit lifecycle cannot undermine access checks.
- Unit activation, shutdown cleanup, kernel identity rejection, journald delivery and reboot retention, resource limits, bounded concurrency, boot activation and on-demand crash recovery have been manually verified on the disposable VM (see test log); these are not yet comprehensive automated deployment tests. Do not remove existing operator database ACLs.


## Disposable systemd integration admission gate (not a deployment)

Before conducting an actual broker systemd test, create a **new** Ubuntu 24.04
VM whose short hostname begins with `uddns-broker-test-`. Do not reuse
`uddns-prealpha` or `uddns-restore-test`. Provision a plain root-owned,
mode-0644 file named `/etc/universalddns-broker-disposable-test` containing
exactly `UNIVERSALDDNS_DISPOSABLE_BROKER_TEST_V1`, and run:

```bash
bash tests/deployment/check-operator-broker-preflight.sh --preflight
```

This opt-in **read-only admission check** refuses unexpected VM names, missing
systemd/virtualization, existing operator sockets/units and root execution.
It never installs, enables, starts, stops, or removes services. Passing it does
**not** establish working systemd activation, runtime privileges, cleanup, or
suitability for SQLite ACL migration. Separate scripted integration tests must
prove those behaviors before any deployment beyond the disposable guest.


## Pre-alpha readiness review — 2026-10-16

| Required gate | Evidence | Remaining work |
| --- | --- | --- |
| 1. Secure Unix socket lifecycle | Disposable VM verified mode/ownership, activation, cleanup, boot, and crash reactivation; isolated unit/activation tests pass | Automated deploy/rollback validation and production threat review |
| 2. Strict bounded protocol | Versioned ping-only protocol, bounded requests/responses, deadlines and tests | Add versioned schemas and independent validation for any future operations |
| 3. Least-privilege methods | Ping-only; no SQL, credentials or DNS mutation exposed | Implement and authorize narrowly scoped admin methods, with negative tests |
| 4. Durable genuine attribution | Kernel-derived operator and redacted journald events; journal persisted over one guest reboot | Retention policy, failure/drop behavior, sensitive issuance semantics, and tamper-resistance review |
| 5. Peer/security and lifecycle | Root/unauthorized denial, four-worker concurrency, service crash/reboot recovery, configured limits, isolated start-limit containment/reset | Group revocation/stale membership, namespace constraints, sustained flooding, broker-specific failure loops, and upgrade/rollback |
| 6. Separate VM and CLI migration | Dedicated disposable VM, no original VM or ACL changes | Migration and rollback rehearsals **before** any ACL removal; preserve direct CLI meantime |

**Decision:** NOT ready for privileged mutation endpoints, replacing the
operator CLI, changing direct SQLite ACLs, production rollout, or publishing
a new pre-alpha release based solely on these broker tests. The ping-only
service is a proven experimental foundation, not an administrator security
boundary for database mutations yet. Review each remaining gate separately.
