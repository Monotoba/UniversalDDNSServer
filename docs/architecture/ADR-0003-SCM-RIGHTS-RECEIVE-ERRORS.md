# ADR-0003: SCM_RIGHTS receiver errors and recovery

PR #161 exercises the low-level receiver's error translation using a
Unix-domain peer with genuine SO_PEERCRED and an injected recvmsg error.
EMFILE (process descriptor exhaustion), ENFILE (system descriptor exhaustion),
EINTR (interrupted syscall), ECONNRESET, and repeated ENOBUFS errors must
fail closed as "handoff unavailable". After injected failures, a fresh
real SCM_RIGHTS transfer on the same disposable socketpair must succeed,
with its received descriptor closed by the test.

These are deterministic injected syscall errors, **not** actual ulimit
exhaustion, system-wide descriptor pressure, or signal-interrupted kernel
recvmsg. Python may transparently retry interrupted syscalls under PEP 475;
this fixture tests explicit InterruptedError propagation only. The injected
error does not dequeue an already delivered SCM_RIGHTS message. No runtime
code or production deployment is modified.
