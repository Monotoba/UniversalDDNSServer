# Isolated SCM_RIGHTS snapshot descriptor handoff

This is a **prototype only**, not a listening service or broker operation. The sender validates Linux Unix peer credentials using SO_PEERCRED, validates a mode-0600 producer-owned regular single-link snapshot, and passes a read-only file descriptor via SCM_RIGHTS. The receiver likewise checks peer UID and descriptor ownership, mode, link count and access flags, closing rejected descriptors.

The caller must obtain authorized peer identities from trusted configuration; never a request field. Linux stream socket peer credentials are connection-level, not proof of the logical caller when file descriptors for the socket are delegated. The tests use local datagram socketpairs and do not establish real cross-UID separation.

A descriptor grants access to the underlying inode, not authority over freshness, record correctness or provenance. No consumer has yet been integrated; the returned descriptor must be independently read and validated against generation and expiry policy. The existing path-based reader cannot yet accept this descriptor. A 0600 owner-only snapshot remains inaccessible via direct file path for a different UID, by design.

Before deployment, require socket pathname/ancestor hardening, cross-account process tests, exact credential matching, descriptor lifecycle/FD-leak tests, resource limits, integration with the consistent reader, and a trusted freshness mechanism. Do not expose a network listener, broker method, or ACL changes.
