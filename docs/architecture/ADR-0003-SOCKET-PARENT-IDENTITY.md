# ADR-0003: Parent directory identity on socket cleanup

PR #145 extends the isolated `OwnedUnixListener` cleanup guard.
The wrapper records the parent directory's device and inode when created.
At shutdown it refuses to unlink a socket path unless the pathname still
resolves through that same owned 0700 directory. It still checks the socket
inode before unlinking. If the directory is replaced, renamed away, made
world-accessible, or otherwise loses its identity, shutdown closes FDs but
leaves pathname cleanup to a separately trusted coordinator.

The regression tests rename and replace the private directory with a new
0700 directory containing an unrelated AF_UNIX socket; shutdown must not
delete that socket. A permissions-drift case likewise preserves the endpoint.

The pathname validation and unlink are still distinct operations, so a
same-UID attacker with directory-mutation capability may race them. This
is an isolated lifecycle improvement, not a production-grade directory-FD
atomic unlink primitive; ancestor directories and directory ownership
remain separate trust concerns. No production services or VM changes.
