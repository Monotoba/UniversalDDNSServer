# ADR-0003: Directory-FD-relative socket cleanup

PR #146 pins the already-private (0700) owner-controlled Unix-socket
parent directory using O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC. Shutdown
checks both the parent pathname identity and the held directory descriptor
before inspecting and conditionally unlinking the original socket name
relative to that descriptor via os.stat(dir_fd=..., follow_symlinks=False)
and os.unlink(dir_fd=...). Directory renaming or substitution therefore
cannot redirect the unlink into a different parent. The directory fd is
closed on graceful completion, failure, or repeated close.

Tests cover rename/substitution, symlink replacement, idempotent cleanup,
private parent permissions, ordinary restart, and simulated process crash.

**Residual limits:** the separate stat and unlink operations are not atomic.
An actor with write authority in the original directory could still swap an
entry between those operations. The pathname used to bind the socket is
also not an atomic bindat operation. This is an isolated fixture, not a
production service deployment or a complete same-UID threat boundary.
