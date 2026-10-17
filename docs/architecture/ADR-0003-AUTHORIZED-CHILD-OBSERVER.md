# ADR-0003: Isolated authorized-child publication observer

PR #113 prototypes `publish_with_authorized_child` using an explicitly
parent-created forked child and a private one-way multiprocessing pipe.
The parent retains its own volatile issuance registry. It invalidates existing
issuance before launching the child, accepts a generation only if the child
reports one, exits cleanly, and the parent independently reads the exact same
generation from the published snapshot. Failures close both descriptors,
terminate/reap the child, and leave the registry invalid.

This is **not** an authenticated arbitrary-process IPC protocol. Authorization
is based on the parent's direct control over creating the child, its private
pipe endpoint, and child exit-status observation. It cannot securely accept
messages from independently started or compromised processes. It also does
not make directory fsync, process exit and registry issuance atomic.

**Unresolved publication race:** verification and issuance do not retain the
producer's persistent flock across the entire observer transaction, and
another publisher can change the target immediately after validation. An
already issued old generation can remain accepted if an independently
authorized process publishes a newer snapshot. Thus the fixture must not be
used as a multi-writer or generally trusted observer. Exclusive writer
ownership and an observer-mediated publication lifecycle must be designed
and tested before any service integration.

Tests cover child success, source failure following previous issuance, forged
or mismatching child acknowledgements, abnormal child exit after sending a
message, invalid timeouts, and registry isolation. Every path uses disposable
test data; no broker, VM, service, live SQLite, account, ACL, DNS publishing,
or release is touched.
