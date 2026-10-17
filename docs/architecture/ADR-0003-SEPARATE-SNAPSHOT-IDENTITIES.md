# Separate producer and reader identity — candidate handoff

**Status: isolated API/fixture only; deployment remains blocked.**

The standalone `read_consistent_snapshot(path, trusted_producer_uid=...)` API now permits a reader process to validate ownership against a configured producer UID instead of requiring its own UID. The producer UID is privileged configuration, **never client-supplied**. Existing same-UID fixture behavior is preserved when the argument is omitted.

This alone does **not** grant a distinct reader access to mode 0600 files. That is deliberate: do not widen to group-readable/world-readable files, reuse the producer service identity, or change live SQLite ACLs. A trusted intermediary with explicit authorization could securely open and verify the snapshot, then transfer a read-only descriptor to a reader, but that intermediary and descriptor-transfer protocol are **not yet implemented**. Alternatively design and review private access via narrowly targeted POSIX ACLs for immutable published snapshots and directory traversal; this changes the security model and requires explicit deployment authorization.

Additional deployment gates: verify caller provenance, secure ownership of every ancestor, replacement and descriptor handling, end-to-end reader isolation, and OS-enforced memory/time caps. Do not wire into broker.
