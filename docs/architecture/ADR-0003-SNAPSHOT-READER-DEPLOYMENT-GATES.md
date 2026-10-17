# Snapshot reader deployment readiness — security gate

**Status: NOT READY for broker integration or VM deployment.** These are requirements, not proof of a secure deployment.

## Ownership mismatch

The standalone producer creates snapshots mode 0600 and the reader currently requires ownership by its **own** effective UID. This is incompatible with the intended distinct producer and least-privileged reader accounts. **Do not change to group-read permission or shared identities merely to make tests pass.** Design a separate transfer/publish identity and a least-privilege reader before use, and ensure neither broker nor reader can write live SQLite or snapshots.

## Filesystem trust boundary

The reader pins a file descriptor and validates the file type, owner, hard-link count, mode, and before/after timestamps. It does not validate the containing directory or every ancestor. An attacker able to replace a parent directory or mutate bytes under the same inode may defeat path or timestamp-only assurances. The producer also relies on cooperating `flock` participants; lock holders and staging paths require a defined ownership and lifecycle policy.

## SQLite/data boundary

The in-memory reader rejects WAL format, malformed headers, invalid generation rows, and bad aggregate flags. Its 64 MiB file cap is **not a total memory cap**; deserialization and SQLite queries can allocate more. A progress handler is not a hard wall-clock limit. Stress tests with malformed pages, large counts, and resource limits remain necessary.

## Freshness and provenance

Generation UUIDs and embedded creation timestamps are not credentials or authenticated freshness markers. Filesystem mtime and a self-reported timestamp may be forged. An external trusted freshness source or authenticated publication protocol must be specified before reporting authoritative counts. Counts describe **staged catalog metadata**, not applied DNS records.

## Go/no-go requirements

- Document and test distinct producer/reader principals and directory traversal permissions, without widening live database ACLs.
- Pin directory ancestry and reject unsafe substitutions, or select an equivalent provably confined handoff.
- Bound CPU, address-space memory, file size and operation time at the process/service level.
- Test malformed or corrupted SQLite pages, hard links, symlink substitutions, concurrent replacements and abrupt process termination.
- Verify freshness from a trusted source and define stale/missing/corrupt fail-closed behavior.
- Run security acceptance on the disposable broker VM only after explicit deployment approval. Keep the other VMs unchanged.

**Decision:** maintain standalone isolation; no broker protocol extension, systemd service, ACL migration, or release.
