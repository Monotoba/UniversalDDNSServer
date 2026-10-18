# ADR-0003: Duplicate pidfds before identity validation

PR #155 moves the registry's pidfd identity validation to the independent
descriptor returned by `os.dup`, eliminating the check-then-dup interval
in which another thread may replace the caller's original FD number.
The registry sets FD_CLOEXEC, verifies the expected PID using the duplicate's
Linux fdinfo, and stores it only after validation. A failed validation or
descriptor setup closes the duplicate. Failed duplication preserves registry
state. Public APIs and capacity/sealing semantics remain unchanged.

Deterministic tests substitute the caller's original FD number immediately
after duplication, force a non-pidfd duplicate, and exercise a bad source FD.
The registry's process-local RLock serializes its own operations but cannot
protect caller-owned descriptor numbers before duplication. Caller-side
races preceding the dup syscall remain a responsibility of the caller:
the registry validates whichever kernel object was actually duplicated.
This does not discover unknown socket holders, enforce directory-writer
exclusion, or make unlink atomic. No production deployment changes.
