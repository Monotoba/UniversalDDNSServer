# ADR-0003: Disposable RLIMIT_NOFILE kernel receive acceptance

PR #162 runs a real AF_UNIX SCM_RIGHTS sendmsg/recvmsg sequence in a
separate Python subprocess. Only the subprocess reduces its soft
RLIMIT_NOFILE, fills its descriptor table to actual EMFILE, and then
invokes the repository's receiver on a queued descriptor transfer.
The receiver must fail closed. The child subsequently frees descriptor
capacity, sends a new transfer, and verifies that the receiver succeeds.
The parent asserts bounded execution (15-second timeout), zero child exit
status, and a success marker.

This is **real process-local** descriptor exhaustion, not system-wide
ENFILE, and does not exercise production services or daemon limits.
Kernel behavior under exhausted receive capacity may differ across
platforms; this fixture is Linux-only. The parent and other CI jobs
retain their normal resource limits.
