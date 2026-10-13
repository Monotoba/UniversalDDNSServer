# RFC 2136 conditional updates and recovery scan

The first-party RFC 2136 adapter now supports `publish_if_contains(expected, replacement)`, which sends RFC 2136 value-dependent prerequisites for each expected RDATA together with RRset replacement in one signed update. It rejects stale values on an isolated BIND 9 server.

**Important limitation:** RFC 2136 does not provide an atomic exact RRset comparison. An RRset containing all expected values *plus additional values* may satisfy the prerequisites. This operation is **not full compare-and-swap**, and should not be used as proof of general multi-writer protection.

`RecoveryWorker.run_once()` performs a bounded scan of expired SQLite leases and checks the authoritative backend through `reconcile()`. If the intended RRset is present, it marks completion; if it differs or observation fails, it does not republish. The worker does not run automatically and does not recover failed intents without expired leases. Retries require an explicit operator action.

Still required before production: authoritative-side conditional coordination for competing writers, a long-running scheduler, lease heartbeats, secure request authentication, policy enforcement on all paths, and failure injection against real BIND.
