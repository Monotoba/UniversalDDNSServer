# ADR-0003: Opt-in peer PID binding for SCM_RIGHTS handoff

PR #127 strengthens the existing isolated AF_UNIX SCM_RIGHTS handoff by
allowing each endpoint to require an exact Linux SO_PEERCRED peer PID,
in addition to its required UID. Invalid or mismatched PIDs fail before
a descriptor is sent or received. The PID is obtained from kernel socket
credentials rather than the untrusted payload. The optional argument
preserves compatibility with existing explicit-UID callers.

A real post-bind fork-and-connect fixture confirms kernel-reported child
PID on the accepted socket and parent PID on the child-connected socket;
both peers require an exact PID and UID before exchanging one read-only,
mode-0600 descriptor. An identity mismatch is refused before consuming
the transfer. Existing checks still cover descriptor owner, access mode,
link count, ancillary truncation and exact one-descriptor payload.

This is a bounded transport and provenance fixture, **not** general
authorization for publishing or trusting a snapshot generation. Linux
SO_PEERCRED describes socket peers at connection time, not a guarantee
that peer code has remained uncompromised; PID reuse, process delegation,
and unrelated privileged peers require appropriate lifecycle controls.
No broker endpoint, VM, production service, filesystem ACL, live database,
DNS publication or release is modified.
