# ADR-0003: Low-level SCM_RIGHTS failure-path descriptor cleanup tests

PR #159 exercises the isolated `receive_snapshot_fd` rejection paths with a
channel adapter retaining real Unix-domain peer credentials but returning
deterministic ancillary SCM_RIGHTS controls. The injected file descriptors
are real OS duplicates. Tests confirm they are closed when reception rejects
multiple descriptors, an unexpected message, truncation flags, a producer UID
mismatch, a writable descriptor, or a non-regular file. The original source
descriptor must remain usable.

This fixture simulates the return value of recvmsg rather than invoking
kernel ancillary-data parsing, and it does not establish kernel-level
MSG_CTRUNC behavior. It directly tests descriptor disposal by the receiver
after recvmsg has delivered the listed descriptors. Each test checks its own
received descriptors, not an unrelated process-wide FD count. Immediate
post-rejection checks rely on no independent descriptor-number reuse in the
disposable single-threaded test. No production runtime changes are made.
