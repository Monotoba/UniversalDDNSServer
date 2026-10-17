# ADR-0003: Same-UID pathname races and safe non-unlinking shutdown

PR #147 distinguishes two isolated listener shutdown policies:

- `owned-path` (compatibility default) performs the previous pinned-dirfd
  stat followed by unlink for matching socket identity. The two operations
  **are not atomic**; another actor able to write the same directory can
  substitute a different entry after the check.
- `preserve` closes the accepted and listening sockets and the pinned
  directory descriptor but **never unlinks** the socket pathname. The
  trusted coordinator must perform separate deliberate cleanup after
  establishing that no attacker can mutate the directory.

Linux offers no exposed `unlinkat-if-inode-equals` syscall. Directory
descriptors prevent ancestor substitution, but do not solve a same-directory
entry replacement race. Advisory locks are not a security boundary against
a malicious same-UID writer. The recommended production design is a
trusted runtime directory with explicitly controlled writer authority and
a coordinator-owned lifecycle. The preserve option offers a fail-closed
interim shutdown policy when exclusive directory control is uncertain.

Tests exercise normal preserve-mode shutdown, same-UID replacement with a
different socket, invalid policy, repeated close and descriptor release.
The change is isolated, opt-in and does not deploy a broker or listener.
