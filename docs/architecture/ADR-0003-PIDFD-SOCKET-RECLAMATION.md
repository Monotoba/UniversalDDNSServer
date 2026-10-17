# ADR-0003: Pinned Linux pidfd as a listener-exit prerequisite

PR #150 adds an opt-in, isolated `reclaim_exited_listener_socket` API.
A supervisor pins a listener PID with `pidfd_open` while it is alive, retains
the descriptor, and subsequently submits the expected PID and pinned fd. The
helper checks the Linux fdinfo PID and polls for process exit before invoking
PR #148's identity-fenced reclamation. Live, mismatched and invalid pidfds
fail closed. A disappeared socket remains an idempotent no-op.

**Scope of the guarantee:** a pidfd proves exit of one pinned process; it
does not prove that this process originally created the socket. The supervisor
must establish that association independently, and must rule out inherited
socket descriptors, descendant listeners and all other pathname writers.
Writer exclusion is still caller attestation, not implementation-enforced.
The stat/unlink pair is not atomic against any remaining directory writer.
The existing reclaim APIs and default listener behavior remain unchanged.

Linux-only disposable tests cover a live listener, SIGKILL exit, wrong and
invalid pidfds, restart and a substituted socket. No deployment or runtime
service wiring is added.
