# ADR-0003: Deterministic sender termination during verification

PR #139 adds an isolated Linux pidfd acceptance fixture. A real child
establishes an AF_UNIX connection and sends SCM_RIGHTS with a one-use
challenge. The parent opens and pins its pidfd before accepting rights.
A controlled test hook wraps the genuine pinned SQLite FD parser and
kills/reaps the child using SIGKILL after the parser returns but **before**
the final pidfd liveness check. The receiver must reject the metadata
despite its valid generation and inode, burn the session, and close the
transferred FD without an increase in the parent's FD count.

The test then exercises an unrelated fresh sender and fresh session to
prove recovery. This accurately covers the critical between-check window;
it is not a guarantee of continued sender liveness after the second
check. The injected test hook is used only by tests; no production
verified-handoff behavior is modified. The existing Linux integration
CI matrix explicitly executes this fixture. No broker, real user,
systemd, ACL, live database, VM, DNS or release change is involved.
