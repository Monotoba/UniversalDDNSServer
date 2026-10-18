# Descriptor-based snapshot reader integration (isolated fixture)

The consistent snapshot reader now provides `read_snapshot_fd(fd, trusted_producer_uid=...)`. It accepts an already-open descriptor, checks that it is read-only, requires private mode 0600, a single link, trusted inode ownership, rollback-mode SQLite and bounded size, then deserializes the same inode and validates generation plus staged-record counts. The caller owns and must close the descriptor; the reader never opens a path.

The path-based API delegates to this same validation. An isolated Unix-domain socketpair test sends a producer-owned snapshot using `SCM_RIGHTS`, receives the FD, removes its pathname, and verifies that the consumer still reads the original generation.

This is **not** a real separate-UID integration test. No broker API or listener was added. Actual cross-UID credentials, socket lifecycle, freshness authentication, and OS resource isolation still require controlled fixture validation. Descriptor delivery is not itself proof of snapshot origin or freshness.
