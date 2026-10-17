# ADR-0003: Inherited pinned descriptor for supervised verification

PR #125 adds an opt-in descriptor argument to the isolated supervised
verifier. In the authorized-observer supervised path, the parent opens the
published snapshot with O_RDONLY, O_NOFOLLOW and O_CLOEXEC, checks the
opened inode against the pre-open lstat, then forks the verifier worker
with that already-open descriptor. The child uses read_snapshot_fd, which
checks read-only access, owner, mode, link count, size and SQLite metadata.
After worker completion, the parent compares the current pathname's inode
to the pinned inode and fails closed on replacement.

The descriptor belongs to the parent and is closed in finally; a worker
inherits it only in the existing fork-only test fixture. Tests distinguish
the pinned older generation from a pathname-reopened new generation after
atomic replacement, reject invalid/writable descriptors, and inject
replacement during supervised observer verification.

No claim is made that this prevents all rename-after-return races or
authenticates an arbitrary external publisher. The observer and producer
still need a mandatory writer-ownership protocol before production use.
No VM, broker, service, production ACL, live database, DNS or release
change is included.
