# ADR-0003: Single-use SCM_RIGHTS transfer challenges

PR #128 extends the isolated descriptor handoff with an optional 32-byte
challenge in the one-byte transfer marker. A parent-created HandoffSession
contains 32 random bytes and a consumed flag. The receiver marks the session
consumed **before** receiving; an incorrect message, missing descriptor or
transport error burns the session. The sender must supply the exact challenge
while satisfying the existing SO_PEERCRED UID and optional PID checks. Only
one read-only descriptor is accepted, and rejected descriptors are closed.

The challenge is a correlation/replay guard for a parent-controlled
single-use session, not a cryptographic proof of arbitrary sender identity.
It is explicitly shared with the authorized sender; compromised authorized
peers can echo it. A new session object with its own challenge is necessary
for each transfer. This volatile state does not survive a restart and does
not authenticate snapshot issuance, generation, or freshness. A sender that
duplicates the challenge on another socket does not gain trust in a consumed
session. Legacy calls without session arguments remain compatible.

Tests exercise matching transfer, incorrect challenge, consumed replay,
stale challenge and invalid challenge types. No broker, VM, systemd, ACL,
production database, DNS publication or release is changed.
