# ADR-0003: Cross-UID handoff failure lifecycle and recovery

PR #135 adds privileged cross-UID acceptance for repeated bad peer identities,
wrong single-use challenges, and publisher disconnects. Each rejection must
leave parent descriptor counts unchanged. After nine rejected transfers the
fixture starts a new publisher/observer Unix socket session and successfully
hands off an authenticated read-only descriptor. The receiving observer checks
generation, inode, its own descriptor count, and that the one-use session
cannot be accepted twice.

The tests execute under explicit sudo in the existing Linux integration
matrix for Python 3.11, 3.12 and 3.13. Processes and file ownership are
limited to disposable test directories. This verifies finite sequential
rejection and recovery, not a proof of unlimited connection flood resilience,
long-running daemon memory stability, or mandatory service authorization.
No production accounts, ACLs, broker, VMs, systemd, DNS or release is changed.
