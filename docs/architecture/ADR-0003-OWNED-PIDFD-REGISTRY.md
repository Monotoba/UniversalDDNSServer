# ADR-0003: Registry-owned pinned pidfds

PR #153 changes the isolated `ListenerHolderRegistry` from borrowing
pidfds to owning non-inheritable `os.dup` copies. During registration it
validates the supplied pidfd's Linux `/proc/self/fdinfo` PID field, duplicates
the descriptor, and closes that duplicate if setup fails. The registry releases
each duplicate on idempotent `close()` and supports context-manager cleanup.
After closure, registration, sealing and reclamation fail closed.

This prevents the caller closing or reassigning its original integer FD from
invalidating the registry's independent kernel process pin. It does **not**
establish completeness of holder enumeration, prove socket ownership or
guarantee another process has no inherited listener descriptor. A registry
seal remains an assertion; writer exclusion remains externally enforced;
stat/unlink remains non-atomic. The registry is not thread-safe and should
be mutated only under trusted single-owner coordination. The caller retains
ownership of its original pidfd. This is disposable Linux-only testing, not
production deployment.
