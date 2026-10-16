# Embedded snapshot generation metadata

**Status:** Standalone experimental producer only. No broker consumer or service.

Each newly published SQLite snapshot contains one `inventory_generation` row with a random UUID generation and integer Unix publication time. The metadata and managed record tables occupy the same SQLite file, so a single atomic rename publishes both. A failed rename preserves the previous generation and snapshot.

This design avoids a separate metadata-file pairing race. It is **not cryptographic authentication**: anyone authorized to mutate the snapshot can change both its records and generation table. Likewise, a local timestamp is not a trustworthy freshness guarantee against file substitution or clock changes.

Deployment requires: restricted producer identity, immutable-to-reader snapshot ownership, a trusted freshness source, access to only consistent generations while replacement occurs, and explicit recovery tests. The existing path-based reader may reopen a different generation; do not connect it to the broker until an inode-pinned read is designed.

No changes to SQLite ACLs, production, VM services, CLI or protocol are authorized.
