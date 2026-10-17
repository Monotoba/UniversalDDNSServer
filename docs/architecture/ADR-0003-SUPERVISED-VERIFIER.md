# ADR-0003: Isolated supervised snapshot verification

PR #123 introduces an independent **opt-in test fixture**, not a replacement
for the publisher-observer production path. A parent forks a verifier child,
which reads the existing pinned SQLite snapshot and returns a fixed-size,
network-order metadata frame. The parent checks the transport length before
reading, imposes one monotonic deadline on the complete frame and worker exit,
requires a clean child exit and EOF, and kills/reaps failed workers.

The returned fields are the generation UUID, creation timestamp, and three
record counts. They are **untrusted snapshot metadata**, not issuance authority.
No registry is populated by this helper. A caller must independently establish
the publisher's authority and coordinate snapshot identity, exclusivity and
freshness; a string or generation from this worker alone proves none of these.

The current fork-based prototype does not protect against an authorized
compromised worker, and file verification in another process does not
eliminate later path replacement. This only places the potentially blocking
SQLite read inside a child the caller can terminate. The parent retains a
limited opportunity for scheduling/cleanup delays and is not a real-time
guarantee. Tests cover success, missing data, stalls, abnormal exit,
unexpected extra frames, invalid timeout and recovery.

No VM, broker, DNS, systemd service, privileged account, ACL, live SQLite
database or release is changed.
