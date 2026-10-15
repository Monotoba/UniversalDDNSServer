# Reconciliation and idempotency (pre-alpha)

- A stable optional `request_key` is scoped per principal and persisted in SQLite. Repeating the same key/payload returns the original intent; changing the payload produces a conflict. Keys must be unpredictable at the public API boundary when introduced.
- SQLite upgrades the prior intent table by adding `request_key` if missing.
- `reconcile(id)` checks the configured authoritative DNS backend. If it observes the exact RRset values **and TTL**, the attempt is marked applied; otherwise the status remains unresolved. An unreachable/non-authoritative server produces an error, never a false negative.
- `reconcile(id, retry=True)` first checks the authoritative RRset. If it matches, the intent is verified without a write. If it differs, retry is permitted only for a `failed` intent with renewed authorization. An `applying` intent is **never** replayed merely because its lease expired: the original DNS request could still be in flight. Explicit retry is **not automatic** and assumes no unrelated writers may change the RRset concurrently.
- The backend can acknowledge updates while caches and other authoritative replicas remain inconsistent. A matching answer proves only the state returned by the configured authoritative server at observation time.

## Process-termination recovery invariant

Publication claims carry persisted ownership tokens and expiration deadlines. A publishing process can terminate after the authoritative server accepts an update but before the journal records success. After restart, recovery must **not** repeat the DNS write:

1. While the original lease remains active, reconciliation skips it.
2. Once the lease expires, the recovery worker observes the configured authoritative server.
3. If the complete RRset matches, the journal marks the intent applied without issuing another write.
4. If the RRset is absent or different, the intent remains unresolved, with no unattended retry. Even an explicitly requested retry is rejected while the intent is still `applying`; an expired lease alone cannot prove the original network write has stopped.

Regression tests simulate process termination using `SystemExit` immediately after a backend write and reopen the persisted SQLite journal before recovery. They cover both observed-success and unresolved outcomes. The suite now includes both deterministic in-process termination tests and a separate POSIX subprocess terminated with actual `SIGKILL`, with its SQLite connection reopened by a fresh recovery worker. The subprocess backend uses a durable marker to simulate an accepted publication; the separate BIND 9 integration suite additionally sends a real signed RFC 2136 update, kills the worker after the server accepts it, and verifies read-only reconciliation. Neither test simulates partial network transport failures or proves exactly-once publication. The current lease does not fence an already in-flight DNS write from a worker whose lease expires.

## Operator handling of stuck applying intents

An expired lease is not permission to repeat a DNS write. First pause automatic publication activity for the affected record and preserve the SQLite database and audit logs. Inspect the intent using the existing operator CLI, inspect the configured authoritative nameserver directly, and attempt read-only reconciliation. A complete match may be marked applied; a mismatch, timeout, or inconsistent authoritative replicas must remain unresolved. Avoid deleting or manually editing journal rows, bypassing ownership checks, or replaying the request solely because the lease expired. An `applying` intent deliberately blocks a subsequent update of the same RRset. If it remains unresolved, isolate any previous workers, establish that outstanding DNS operations can no longer execute, and use a controlled recovery procedure only after reviewing the DNS state and the remaining concurrency risks. The current implementation does not provide a supported automated transition from ambiguous `applying` to safely retryable state; do not represent one as available.

**Remaining safety work:** partial-transport fault injection, stronger multi-writer coordination and DNS compare-and-swap prerequisites, retention/idempotency expiration, broader credential-lifecycle hardening, production HTTPS ingress and rate limiting, revision semantics for concurrent operator edits, complete migration testing, and external DNS integration verification. The project is not production-ready.

## Audited read-only operator assessment (v0.4 development)

The local operator CLI offers an assessment command; it does not alter the intent journal or issue a DNS UPDATE:

```sh
python -m universalddns.operator --config /etc/universalddns/config.json assess INTENT_ID
```

It returns the journal state, whether the configured authoritative RRset matches, an investigation/verification next-action hint, and `retry_safe: false`. Audit events record the intent identifier, starting/completed/error outcome, and comparison boolean without credentials or full DNS answers. For a match, run the separate `reconcile INTENT_ID` operation after lease expiry to persist verified completion. An absent or differing record is **not** proof that the previous update can no longer finish: stop and isolate relevant workers, preserve the journal, and investigate manually. An unavailable authoritative server produces an error rather than a negative observation. This feature deliberately does not provide a manual force-retry, unblock, or erase operation.
