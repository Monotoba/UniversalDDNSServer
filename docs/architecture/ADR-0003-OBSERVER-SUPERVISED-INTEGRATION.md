# ADR-0003: Optional supervised observer verification

PR #124 adds an **opt-in** `supervised_verification=True` parameter to the
isolated `publish_with_authorized_child` fixture. The parent retains sole
volatile issuance authority. After acknowledging a clean publisher exit, it
asks the supervised SQLite verifier for bounded metadata using the remaining
deadline, checks that the returned generation matches the challenge-bound
publication acknowledgement, and only then issues trust. A second supervised
current-path read checks the same generation before successful return.
Both reads compare destination inode identity before/after verification.

The existing default in-process verification path remains unchanged. Failure,
timeout, mismatched generation or pathname replacement invalidates registry
state. Integration tests cover opt-in success, mismatched metadata, delayed
verification after prior trust, pathname replacement and recovery.

This does **not** grant authentication to metadata from a compromised child.
The verifier processes the current path, not an fd pinned across the entire
publication lifecycle. Independent writers can still bypass cooperative
observer locking or replace the file immediately after validation. A
production sole-writer boundary remains necessary. Supervision bounds the
child SQLite read, but parent-side scheduling and filesystem calls are not
hard real-time operations. No broker, VM, systemd, production ACL, live DB,
DNS or release change is included.
