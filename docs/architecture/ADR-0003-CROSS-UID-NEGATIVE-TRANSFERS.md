# ADR-0003: Privileged cross-UID negative transfer acceptance

PR #134 adds four disposable Linux root-gated negative scenarios to the
privileged integration matrix for Python 3.11, 3.12 and 3.13. A publisher
identity (UID 65533) owns the private 0700 snapshot directory; an observer
identity (UID 65534) receives via a connected AF_UNIX socket. Each observer
expects a separate single-use HandoffSession challenge and a previously
observed generation and inode. All scenarios must **reject** the transfer:

- An impostor UID 65532 connects but cannot satisfy SO_PEERCRED UID checks.
- The designated publisher supplies the wrong session challenge.
- The designated publisher sends a different, valid snapshot inode.
- The designated publisher exits before sending ancillary rights.

A rejected attempt must consume the observer's one-use session and must
not return validated metadata. The tests create and clean only temporary
files and short-lived forked processes; they do not change production
accounts, ACLs, services, broker, VM, live data, or DNS.

This checks fail-closed provenance and cleanup, **not** protection against a
compromised authorized publisher, stale independently supplied expectations,
or a publisher process with root-equivalent privileges. As with PR #133,
privileged CI log evidence must show the tests really ran rather than skipped.
