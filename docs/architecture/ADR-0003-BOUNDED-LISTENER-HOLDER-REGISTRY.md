# ADR-0003: Bounded declared listener-holder registry

PR #152 adds an optional in-process registry of pidfd pairs explicitly supplied
by a trusted external supervisor. Registration refuses duplicate/invalid PIDs,
negative descriptors, and capacity overruns (configurable 1–64). A nonempty
registry must be sealed before reclamation, at which point it is immutable.
A declared owner must be present. Reclamation delegates to PR #151's
PID-identity and process-exit validation for every registered holder, plus
the existing socket identity validation.

**Limits:** Sealing records an assertion by the caller, not proof of
completeness. The API cannot enumerate unknown inherited or transferred
descriptors, prove socket ownership, prevent reuse/closure of borrowed pidfd
numbers by a caller, exclude other pathname writers, or make unlink atomic.
The caller must supervise fd lifetime, maintain its own enrollment freeze
across fork/SCM_RIGHTS transfers, and independently establish exclusive
writer control. A malicious/incomplete registry cannot authorize secure
cleanup merely by calling seal. This increment does not wire a production
supervisor, systemd, ACLs, or socket deployment.
