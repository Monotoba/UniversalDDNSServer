# ADR-0003: Optional one-clock handoff session deadline

PR #141 adds an opt-in monotonic absolute `deadline` for
`receive_completed_snapshot`. The deadline is propagated through the
validated descriptor receiver, caps the descriptor-read timeout, and is
rechecked after pinned SQLite verification, before and during each
fragmented acknowledgement read, and after the final peer pidfd check.

This addresses slow-drip completion frames that could repeatedly reset a
per-operation socket timeout. Once the deadline expires, the receiver fails
closed and consumes its single-use session. Passing no deadline preserves
existing legacy timeout behavior. Callers must derive the deadline in
their own trusted parent context, not from sender-provided data. The
underlying pinned SQLite reader still enforces its independent bounded read
and the monotonic handoff deadline is checked on return.

Integration tests cover valid fragmented completion, slow-drip expiry,
expiration between verification and completion, and fresh-session recovery.
No broker service, VM, production account, ACL, database, DNS or release
is changed. This is not an asynchronous preemption mechanism and the
sender may still terminate after the final liveness check.
