# Worker lease primitives

SQLite claims now support persisted expiry and renewal. A leased worker whose deadline expires cannot mark the attempt completed; it is returned by expired_leases() for authoritative-state reconciliation. Expiration does **not** permit blind DNS retry, because network publication may have succeeded.

These primitives are not yet wired into the orchestrator's legacy claim path. Previous claim/finish/requeue methods remain for compatibility and require hardening before public deployment. A lease token fences SQLite state transitions, not in-flight DNS server writes. There is no scheduler, automatic recovery loop or compare-and-swap for existing RRsets. No production readiness is claimed.
