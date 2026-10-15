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

Regression tests simulate process termination using `SystemExit` immediately after a backend write and reopen the persisted SQLite journal before recovery. They cover both observed-success and unresolved outcomes. The suite now includes both deterministic in-process termination tests and a separate POSIX subprocess terminated with actual `SIGKILL`, with its SQLite connection reopened by a fresh recovery worker. The subprocess backend uses a durable marker to simulate an accepted publication; it does **not** exercise real BIND 9 or network-partition behavior. The current lease does not fence an already in-flight DNS write from a worker whose lease expires.

**Remaining safety work:** real BIND 9 process-kill and partial-transport fault injection, stronger multi-writer coordination and DNS compare-and-swap prerequisites, retention/idempotency expiration, broader credential-lifecycle hardening, production HTTPS ingress and rate limiting, revision semantics for concurrent operator edits, complete migration testing, and external DNS integration verification. The project is not production-ready.
