# ADR-0003 follow-up — proposed read-only record inventory contract

**Status:** Design only; no operation implemented or database opened by broker.

## Existing schema and risk

The broker currently supports authenticated `ping` and static `capabilities`. `RecordCatalog` initializes/migrates SQLite schema on construction, so it is **not suitable** for a read-only accessor. The `managed_records` table has `record_id`, `zone`, `name`, `record_type`, `ttl`, `values_json`, `revision`, and `active`. The existing operator `list` includes names and addresses; this proposed endpoint must not. `active` is **staged metadata**, not live DNS publication.

## Proposed protocol (not implemented)

- Version 1 request with exact keys `version` and `operation`, where operation is `record_inventory`; no client-specified paths, SQL, filters, IDs or identity.
- Successful response: `ok: true`, `version: 1`, `total_records`, `staged_active_records`, and `staged_inactive_records`, all bounded nonnegative integers. Verify total equals active plus inactive. Explicitly describe counts as staged catalog state, never runtime publication.
- Never expose record IDs, zones, names, IP addresses, TTLs, credential metadata, raw rows or values_json.
- Authenticate via kernel `SO_PEERCRED` and group policy **before** opening any database. Deny root and unauthorized clients. Audit authenticated successes/failures without data or paths. Return generic errors without leaking SQLite internals.
- Use separate read-only SQLite URI `mode=ro` plus `PRAGMA query_only=ON` with fixed aggregate SQL and verified schema. Never instantiate `RecordCatalog` or migrate schema. Fail closed if the database/table is missing or unexpected. Preserve request/response byte limits and deadlines.
- Do not alter the existing CLI, SQLite ACLs, original VMs, or release.

## Required gates before implementation

1. Test empty, missing, malformed, legacy and concurrent-write SQLite fixtures; demonstrate no files, WAL or journal creation/mutation from reads.
2. Verify zero, mixed, high-count, invalid active flags, database locks and inaccessible database; enforce strict count and execution bounds.
3. Deny unauthorized/root clients before any open; prevent metadata leakage through errors or audit.
4. Preserve exact protocol schema and backwards-compatible ping/capabilities; advertise the new operation only once implemented.
5. Run isolated fixture tests and then dedicated disposable VM testing before any real database permissions or migration change.

**Decision:** Counts-only staged inventory is the smallest database-backed observation worth implementing, but it is not authorized for deployment by this design document.
