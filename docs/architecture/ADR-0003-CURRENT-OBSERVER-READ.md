# ADR-0003: Current-generation observer read guard

PR #114 adds an explicitly opt-in `read_current_authorized_snapshot`
operation to the isolated observer prototype. Instead of validating a detached
previously read snapshot, callers re-open the *current* published path,
compare its generation with the process-local authorized registry, and
compare the path's device/inode before and after the pinned-descriptor read.
An unobserved publication or an inode replacement during that read rejects
the observation as `snapshot unavailable`.

The parent-authorized publisher also uses this guard when returning its
initial accepted generation. Tests cover successful reads, outside-writer
replacement after issuance, replacement injected within the read operation,
missing files, and symlink rejection.

## Unresolved safety boundary

The guard does **not** revoke a stale registry automatically. The legacy
`registry.validate(previously_read_object)` can still accept the old
generation until invalidated/expired. It also does not provide a
linearizable lease: an independent process can publish *after* the second
inode check. This patch offers no exclusive-writer ownership or durable
cross-process trust. Consumer entry points must not treat a prior validated
object as permission to rely on the current published path.

An actual observer-mediated singleton publisher protocol must fence all
writers and coordinate reads and issuance across process boundaries before
production integration. No broker, VM, systemd, account, ACL, live database,
authoritative DNS, or release was modified.
