# ADR-0003: Cross-process publication and crash-boundary acceptance

PR #112 adds Linux fork-based isolated acceptance fixtures for the pre-integration
snapshot publication adapter. These fixtures do **not** authorize any production
observer, broker binding, systemd service, privilege change, or database access.

## Guarantees demonstrated

- The snapshot producer's persistent lock inode and nonblocking `flock`
  reject a competing publisher process while an initial publisher holds its
  lock. The separate `threading.Lock` in the acknowledgement adapter is
  **process-local** and does not provide that cross-process exclusion.
- A competing publication process cannot establish issuance in the parent
  observer's volatile registry. A new registry also refuses a snapshot without
  its own trusted successful acknowledgement.
- Forced child termination is tested immediately before rename, immediately
  after rename but before directory fsync, after directory fsync but before
  acknowledgement, and after in-child acknowledgement. Snapshot generations
  may change at the latter three points, yet the independent observer remains
  unissued and must fail closed.
- The next isolated successful publication removes eligible abandoned staging
  files left by crashes and restores issuance **only in its own process**.

## Important remaining hazards

A parent registry that issued an earlier generation does not automatically
notice an out-of-process publisher. It may continue accepting a pinned **old**
generation until invalidated or expired. A shared authoritative observer or
cross-process revocation protocol is therefore required before deployment.
These tests explicitly invalidate the parent observer before permitting an
uncoordinated child publication; they do not assert that this happens today
without coordination.

An atomic rename, directory fsync, and volatile registry issuance are not an
atomic distributed transaction. The post-rename/pre-fsync crash boundary
cannot guarantee persistence after power loss merely because the file appears
after a simulated process termination. The post-acknowledgement child can lose
all trust on restart even though the published bytes survive.

The publisher's cooperative `flock` can be bypassed by direct writes or
by malicious same-UID processes; it authenticates neither observer nor
publisher. There is no restart-persistent authenticated manifest and no
production IPC observer. The tests use disposable private directories and
synthetic SQLite databases only. No live database, broker, VM, systemd
unit, ACL, DNS publication, or release is changed.
