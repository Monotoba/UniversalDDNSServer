# ADR-0003 — Inventory snapshot boundary (proposal)

**Status:** Design and isolated fixture only. No live database access, broker integration, service or permission changes.

## Finding

`mode=ro` and `PRAGMA query_only` prevent SQL writes, **not** necessarily WAL shared-memory sidecar updates. Checking a SQLite file header and `-wal`/`-shm` existence before opening is subject to time-of-check/time-of-use races. SQLite `immutable=1` is not a safe substitute for a coherent snapshot of a changing database: it assumes the file cannot change and can miss live WAL contents.

## Proposed trust boundary

1. A separately authorized **snapshot producer**, never driven by arbitrary client parameters, opens the source database using supported SQLite transaction/backup semantics, including the WAL state. It runs under a deliberately scoped service identity and may legitimately participate in SQLite sidecar coordination. This is *outside* the broker and requires its own deployment and security review.
2. Produce a consistent, complete **standalone rollback-mode SQLite copy** in a protected staging directory on the same filesystem as its final snapshot destination. Confirm it has the expected schema and counts; explicitly verify the snapshot header has read/write format bytes `01 01`, and no WAL/SHM dependencies. Do not claim a raw database-file copy captures uncheckpointed WAL transactions.
3. Publish snapshots by atomic rename into a **private, operator-unwritable directory** only after creation, validation, file permission setting and syncing appropriate to the retention requirement. Address symlink substitution, hard links, ownership, staging cleanup, stale generation, retention, disk exhaustion and replacement during an active read. A manifest/generation identifier may be needed to bind data and freshness metadata.
4. The broker must never open the *live* SQLite path. It may eventually read only a prevalidated, unchanging snapshot using a dedicated low-privilege reader, once freshness and replacement race handling is demonstrated. The current standalone `record_inventory` accessor remains **unwired**.
5. Define an explicit freshness policy: stale/missing/corrupt snapshots return a generic unavailable error rather than silently suggesting counts represent the current catalog or DNS publication state. Audit the result without exposing paths, raw record values or secrets.

## Required validation before implementation

- Fixture with WAL mode, uncheckpointed committed writes and a concurrent writer: snapshot must include exactly committed rows at a transactionally consistent point and exclude uncommitted rows.
- Confirm snapshot production does not alter live record content, schema, ACLs or issue credentials; characterize expected WAL/SHM coordination writes honestly.
- Read snapshot through the existing accessor while measuring its bytes and directory entries before/after; source is never accessible to the broker path.
- Verify broken or missing snapshot, truncation, wrong journal mode, symlink replacement, permission errors, stale snapshot, concurrent atomic replacement, and disk-full/failed producer cleanup.
- Run failure/rollback tests on disposable isolated fixtures, then dedicated guest. No SQLite ACL removal until separately approved migration gates pass.

**Decision:** Do not connect live WAL databases to the broker. Advance first with an isolated snapshot-producer fixture demonstrating backup consistency; deployment and ownership design are pending.
