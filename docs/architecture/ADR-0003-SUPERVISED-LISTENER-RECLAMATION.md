# ADR-0003: Local supervised-listener shutdown gate

PR #149 introduces `reclaim_closed_owned_listener` as an opt-in companion
to PR #148's existing explicit identity-fenced reclamation API.

The new gate receives an actual `OwnedUnixListener` instance rather than
an arbitrary inode tuple. It requires preserve mode, a released pinned dirfd,
a closed listening socket, and a recorded socket identity. These checks
establish only **local object lifecycle**, not kernel-wide process death.
On success it delegates to the existing directory-relative identity checks.

The caller still must establish writer exclusion independently. A boolean
attestation is not a security boundary. A same-UID adversary capable of
mutating the directory can defeat stat-then-unlink atomics even with this
wrapper; ownership of a 0700 directory is insufficient. A supervisor
controlling process lifetimes and a directory managed by a separate trusted
principal are necessary before production use. Do not infer process exit
from failed socket connect. No production orchestration is added here.

The original API and listener semantics remain unchanged. Explicit tests
cover an open listener, trusted recovery, wrong cleanup mode, substituted
socket, and unsupported object. All tests are disposable fixtures.
