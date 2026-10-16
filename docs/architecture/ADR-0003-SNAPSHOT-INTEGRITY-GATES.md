# Snapshot integrity and publication interruption — gate review

**Status:** Research and test increment only. The producer remains disconnected from the broker.

An ordinary SHA-256 fingerprint detects content changes when compared against a previously trusted expected value. A checksum stored beside the database is **not authentication** when the same attacker can replace both. The new fingerprint primitive does not by itself prove snapshot freshness, producer identity, generation order, or safe publication.

## Publication state model

1. Acquire a validated persistent lock.
2. Remove only safely validated orphan staging files.
3. Produce a complete SQLite backup in a private staging file.
4. Validate the snapshot, compute a content fingerprint, and fsync its content.
5. Atomically replace the destination and fsync the directory.

Termination before replacement leaves the previous published snapshot intact; cleanup is attempted by a later publisher holding the exclusive lock. Termination after replacement but before directory fsync leaves durability contingent on the filesystem and crash behavior. Do not promise crash-durable publication across power loss without explicit filesystem fault testing.

## Deferred work before a trusted manifest

- Bind generation, trusted creation timestamp, SHA-256 and database counts in a tamper-resistant publication mechanism; do not create a separate freely replaceable JSON manifest and claim it authenticates the snapshot.
- Ensure an atomic read of matched metadata and database generation, with stale or mismatched generations failing closed.
- Prove cleanup against abrupt subprocess termination and shared filesystem power-loss simulation when available.
- Strengthen source/target ownership and symlink confinement; resolve current publication races.
- Require a distinct low-privilege snapshot reader, without permission to mutate the live source or published objects.

No new broker operation is authorized by this document.
