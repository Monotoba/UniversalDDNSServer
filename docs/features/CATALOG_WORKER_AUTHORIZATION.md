# Catalog authorization at worker publication

The runtime Policy now reads a fresh SQLite snapshot of staged-active catalog entries and unrevoked credential grants each time the update orchestrator checks permission, including immediately before calling the RFC 2136 backend. Deactivating an entry, removing the token or changing its RRset key causes subsequent authorization checks for the old record to fail. Static configured records remain permitted only through explicit grants.

**Scope:** This authorizer does not by itself enable REST submissions for catalog records. The HTTP write endpoint remains static-config-only. This change prepares the worker to safely evaluate dynamic intent records once the API enables them.

**Concurrency limit:** The final authorization check and the remote DNS write are separate operations. Revocation or deactivation racing after authorization can still allow an in-flight DNS operation to finish. This is not a DNS-side fence, not a safe force-retry mechanism, and not a production readiness claim. Live activation requires an explicit concurrency protocol and isolated BIND 9 testing.
