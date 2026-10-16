# ADR-0003 — Privileged local administration broker (proposed)

**Status:** Proposed; foundation implemented, not enabled. **No** new network service, socket listener, or replacement CLI is deployed.

## Problem

The experimental local operator CLI needs `rwx` on the SQLite parent and `rw-` on the state database. This means authorized human users can edit credentials, records and audit entries outside the CLI, bypassing its validation.

## Decision direction

Introduce a minimal single-host administration broker running under a dedicated, non-login identity with access to the SQLite state, not the TSIG secret. Use a Unix-domain socket under a root-managed runtime directory. Its clients need only permission to connect; human users should lose direct database write permission **after** a separately tested migration.

Authenticate connecting clients from kernel `SO_PEERCRED` on Linux, then check the numeric UID against the local `universalddns-operators` group. Reject UID 0 and invalid/unrecognized peer identities. Do not trust any username, UID, or role supplied by request JSON. The initial `operator_peer` helper provides only this authentication primitive, not a hardened broker.

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
