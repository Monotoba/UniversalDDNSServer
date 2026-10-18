# ADR-0003: Targeted SCM_RIGHTS descriptor closure assertions

PR #156 strengthens isolated handoff leak tests without modifying runtime code.
Tests capture the actual received SCM_RIGHTS descriptor at the snapshot-read
boundary and check that it becomes invalid after normal verification,
stale-generation rejection, or sender SIGKILL during verification. The
successful case additionally checks that an independently held reference
descriptor remains valid.

Previously a whole-process `/proc/self/fd` count was used in these paths.
Such counts can decrease when unrelated descriptors close and can conceal
a leaked descriptor if another FD closes concurrently. The new assertions
test the specifically observed descriptor lifecycle instead. These tests
assume no unrelated actor reuses the observed descriptor number during the
immediate post-call check. This is a controlled disposable fixture, not a
general process-wide leak detector or proof of safe cross-thread reuse.

No runtime behavior, production service, account, ACL, DNS or release changes.
