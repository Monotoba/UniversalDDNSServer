# ADR-0003: Cross-UID handoff descriptor-specific recovery checks

PR #158 replaces broad /proc/self/fd count comparisons in the privileged
cross-UID negative-transfer fixture with a targeted observation of the
SCM_RIGHTS descriptor delivered during successful recovery. The observer
captures the descriptor at the verified snapshot-read boundary and requires
that the verifier closes that exact descriptor after success. Session replay
must still be rejected. Repeated wrong-UID, wrong-challenge and crash cases
must continue to fail, followed by successful fresh-session recovery.

The parent still waits for sender/observer process exit and checks child exit
status; process termination reclaims child-owned resources. The tests no
longer assert that global FD counts remain numerically identical through
unrelated activity. Failure modes rejected before the read boundary are
not covered by the success-path targeted FD check. Immediate fstat closure
checks assume no unrelated FD-number reuse inside the disposable observer.
Runtime code and production state remain untouched.
