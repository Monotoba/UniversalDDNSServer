# ADR-0003: Serialized listener-holder registry lifecycle

PR #154 adds a per-registry reentrant lock that serializes registration,
sealing, reclamation and closure. It prevents close from releasing owned pidfds
while an in-process reclamation is using them, and prevents sealing an
incompletely registered holder while a registration is in flight.
Repeated close remains idempotent; operations after close fail closed.
Context-manager entry observes closure under the same lock.

The lock is process-local. It does not coordinate a separate process, prevent
fork/SCM_RIGHTS descriptor transfers, or prove an externally supplied holder
registry is complete. It does not enforce directory-writer exclusion, establish
socket ownership, or make the stat/unlink operation atomic. Caller-supplied
pidfds must not be concurrently replaced during registration; the registry
still owns independent duplicates after successful registration.

Two isolated deterministic tests use threading Events to hold operations
inside their critical sections while another operation attempts to advance.
No production process supervision or deployment is changed.
