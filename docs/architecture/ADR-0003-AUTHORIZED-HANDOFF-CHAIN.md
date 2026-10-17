# ADR-0003: Parent-authorized publisher to session-bound descriptor issuance

PR #130 provides an **opt-in isolated fixture**, `descriptor_handoff=True`,
which gates the existing parent-only issuance on successful descriptor handoff.
The original observer independently launches a child publisher, verifies its
challenge-bound durable-publication acknowledgement, requires clean child exit,
and reads the current snapshot. Before registry.issue, the parent creates a
fresh single-use SCM_RIGHTS session and separate forked sender that connects
to a private abstract AF_UNIX listening socket. The parent checks the
kernel-reported sender UID and exact PID, expected device/inode, pinned SQLite
metadata, exact acknowledged generation and deadline. It requires the sender's
clean exit and verifies the current pathname inode before issuance. Failures
invalidate issuance and reap child processes.

This is **not** a mandatory writer authorization boundary: the transfer
sender is parent-created after publishing, not the original publisher
process, and the same-UID producer may still independently replace the
snapshot. The transfer challenge and connection bind an authorized session,
not a cryptographic assertion that external producer code is uncompromised.
A replacement immediately after the final inode observation remains possible.
The legacy default path is preserved. No production broker, VM, systemd,
ACL, live SQLite, DNS publication or release is changed.
