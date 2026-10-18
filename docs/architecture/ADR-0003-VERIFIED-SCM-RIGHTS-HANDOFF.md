# ADR-0003: Session-bound descriptor generation verification

PR #129 introduces an additive, isolated receive helper that consumes one
HandoffSession, requires kernel peer UID and optional PID checks through the
existing SCM_RIGHTS receiver, and validates the received read-only descriptor
using the pinned-fd SQLite reader. The caller supplies an independently
authorized **expected generation**, plus an optional expected device/inode
identity recorded from a trusted source. The helper compares metadata and
descriptor identity before returning, closes the descriptor on all paths,
and burns the session after failure.

The helper **never** issues a SnapshotIssuanceRegistry generation. A transfer
challenge proves only session correlation. The sending peer and descriptor
cannot self-authorize the expected generation; it must originate from a
separately authorized and observed publication. An optional inode comparison
helps reject substitution but cannot prevent later pathname replacement or
all concurrent file mutation. This remains an isolated same-UID test fixture,
not a deployed authenticated broker protocol.

Tests cover generation agreement, stale generations, swapped snapshot
descriptors, inode mismatch, failed-challenge consumption and descriptor
cleanup. No VM, service, production account or ACL, live SQLite, DNS or
release changes are included.
