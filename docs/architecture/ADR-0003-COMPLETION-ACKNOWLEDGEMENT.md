# ADR-0003: Opt-in parent-controlled handoff completion echo

PR #140 introduces an isolated two-way completion exchange after the
receiver independently verifies the SCM_RIGHTS descriptor, expected
generation, inode, and pinned sender pidfd. The receiver sends a fixed
33-byte `V + session.challenge` frame. The still-live sender echoes
`A + session.challenge`. The parent refuses mismatched, truncated or
timed-out responses and performs a final pidfd liveness check. A receiver
session remains single-use regardless of success or failure. Legacy
`receive_verified_snapshot` callers are unchanged.

Tests cover successful completion, wrong/replayed response, silent sender
timeout, exited sender, consumed-session replay, and subsequent fresh
session recovery, across Python 3.11–3.13 integration jobs.

This handshake is *not* cryptographic authentication, persistent issuance
or an atomic guarantee of peer survival after the final poll. The sender
already knows the challenge, and an authorized but compromised peer could
echo it. A production broker must separately authorize publisher identity
and generation, enforce an overall deadline, and avoid relying on the echo
as the sole trust anchor. No deployed service, VM, ACL, DNS or production
database is modified.
