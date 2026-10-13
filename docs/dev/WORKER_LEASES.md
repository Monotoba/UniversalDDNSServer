# Worker lease enforcement

The orchestrator claims pending jobs using SQLite-backed bounded leases. Completion requires the same token and an unexpired lease. Legacy unfenced claim() and finish() are disabled. Existing claim_owned() now delegates to bounded leases.

A still-active lease cannot be requeued or marked verified. Expired operations remain ambiguous and require authoritative DNS reconciliation; expiration alone never triggers a publish. Interrupted network operations may outlive their local leases, so SQLite fencing does not fence DNS writes at the authoritative server.

This is an incremental safety improvement, not a production recovery scheduler. Heartbeats for long-running writes, atomic compare-and-swap for existing RRsets, retry scheduling, reliable audit logging, and stronger failure injection remain outstanding.
