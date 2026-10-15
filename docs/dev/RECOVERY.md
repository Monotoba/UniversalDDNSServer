# Reconciliation and idempotency (pre-alpha)

- A stable optional `request_key` is scoped per principal and persisted in SQLite. Repeating the same key/payload returns the original intent; changing the payload produces a conflict. Keys must be unpredictable at the public API boundary when introduced.
- SQLite upgrades the prior intent table by adding `request_key` if missing.
- `reconcile(id)` checks the configured authoritative DNS backend. If it observes the exact RRset values **and TTL**, the attempt is marked applied; otherwise the status remains unresolved. An unreachable/non-authoritative server produces an error, never a false negative.
- `reconcile(id, retry=True)` is an explicitly requested retry only after the authoritative check shows a mismatch, and rechecks authorization. It is **not automatic** and assumes no unrelated writers may change the RRset concurrently.
- The backend can acknowledge updates while caches and other authoritative replicas remain inconsistent. A matching answer proves only the state returned by the configured authoritative server at observation time.

## Process-termination recovery invariant

Publication claims carry persisted ownership tokens and expiration deadlines. A publishing process can terminate after the authoritative server accepts an update but before the journal records success. After restart, recovery must **not** repeat the DNS write:

1. While the original lease remains active, reconciliation skips it.
2. Once the lease expires, the recovery worker observes the configured authoritative server.
3. If the complete RRset matches, the journal marks the intent applied without issuing another write.
4. If the RRset is absent or different, the intent remains unresolved, with no unattended retry.

Regression tests simulate process termination using `SystemExit` immediately after a backend write and reopen the persisted SQLite journal before recovery. They cover both observed-success and unresolved outcomes. These are deterministic fault-injection tests, **not** a real OS-level SIGKILL or network-partition validation. The current lease does not fence an already in-flight DNS write from a worker whose lease expires.

**Remaining safety work:** real-process SIGKILL and partial-transport fault injection, stronger multi-writer coordination and DNS compare-and-swap prerequisites, retention/idempotency expiration, broader credential-lifecycle hardening, production HTTPS ingress and rate limiting, revision semantics for concurrent operator edits, complete migration testing, and external DNS integration verification. The project is not production-ready.
