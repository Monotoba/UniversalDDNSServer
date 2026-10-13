# Reconciliation and idempotency (pre-alpha)

- A stable optional `request_key` is scoped per principal and persisted in SQLite. Repeating the same key/payload returns the original intent; changing the payload produces a conflict. Keys must be unpredictable at the public API boundary when introduced.
- SQLite upgrades the prior intent table by adding `request_key` if missing.
- `reconcile(id)` checks the configured authoritative DNS backend. If it observes the exact RRset values **and TTL**, the attempt is marked applied; otherwise the status remains unresolved. An unreachable/non-authoritative server produces an error, never a false negative.
- `reconcile(id, retry=True)` is an explicitly requested retry only after the authoritative check shows a mismatch, and rechecks authorization. It is **not automatic** and assumes no unrelated writers may change the RRset concurrently.
- The backend can acknowledge updates while caches and other authoritative replicas remain inconsistent. A matching answer proves only the state returned by the configured authoritative server at observation time.

**Remaining safety work:** ownership leases, multi-worker races, robust compare-and-swap DNS prerequisites, retention/idempotency expiration, credential store, secure HTTP API, revision semantics for concurrent operator edits, complete migrations, and external DNS integration verification. The project is not production-ready.
