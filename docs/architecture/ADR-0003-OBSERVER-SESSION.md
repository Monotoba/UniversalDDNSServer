# ADR-0003: Cooperative observer-session exclusion

PR #115 adds an isolated, opt-in observer-session context manager around
parent-authorized publication and current-generation reads. A persistent,
nonblocking `flock` on `.inventory-observer.lock` in a private directory
coordinates **cooperating** observer processes. A failed attempt does not
revoke the incumbent observer's issuance. The kernel releases the file lock
following process death, and the lock inode is never unlinked.

The observer lock is distinct from the producer's
`.inventory-publish.lock`. The parent holds the observer session throughout
child publication, acknowledgement and validation, so the child can acquire
the producer lock without self-deadlock. A participating reader acquires the
observer session throughout its current-path generation and inode checks.
Tests cover process-level contention, lock survival/recovery, valid
publication and read, and malicious symlink lock paths.

**Not a globally exclusive writer:** direct users of
`publish_inventory_snapshot` do not acquire the observer-session lock.
Same-UID malicious processes and direct filesystem mutation also bypass it.
These fixtures do not attest publisher identity across arbitrary processes or
revoke a previously issued generation on uncoordinated publication.
No cross-process read lease persists beyond return. A production solution
must establish sole-writer privileges and channel authorization, then test
them before service integration.

No changes to broker, VMs, systemd, live database, ACLs, DNS, or releases.
