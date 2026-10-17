# ADR-0003: Pinned descriptor lifecycle and number-substitution fencing

PR #126 adds an explicit parent-side identity check to the isolated
supervised-verifier pinned-file-descriptor path. At entry, the verifier
checks that the descriptor is a regular, read-only, linked file and captures
its device/inode. After the supervised worker exits, it rechecks device/inode,
link count, and access mode before accepting its bounded metadata. The
worker separately validates the inherited descriptor's owner, mode,
link count and SQLite bytes.

Tests use an isolated disposable directory and `dup2` to replace the
parent's descriptor number after the child has read the original inode:
the metadata must be rejected. A second fixture repeatedly stalls a
verifier worker, checks process/FD cleanup, then successfully reads again.

These tests do not constitute an authenticated descriptor-transfer
mechanism. In the fork-only fixture the descriptor is inherited, not
transferred by an authenticated external IPC channel. A same-UID
malicious process may still bypass cooperative locks, and substitution
followed by restoration between identity checks is not prevented.
Production service wiring, privileges, ACLs, VMs, DNS and releases are
unchanged.
