# Process-local snapshot issuance contract (isolated)

The `SnapshotIssuanceRegistry` holds one generation and monotonic issuance time in process memory. A new instance, invalidation or PID change **fails closed**. A new issuance replaces the prior generation and rejects backward clock events; the existing freshness validator rejects mismatched generations and snapshots older than 300 seconds.

**Not authenticated across processes.** This registry intentionally has no disk format, cryptographic signature, replayable bearer token or persistent shared state. It is safe only if an independently authorized in-process observer calls `issue` **after confirming successful snapshot publication** and does not accept issuance arguments from clients. This authorization path has not yet been implemented, and no broker or publisher calls the registry. Restart requires a new trusted issuance; the old snapshot is not automatically promoted to trusted status.

The process PID guard blocks accidentally reusing copied registry state after `fork`; it does not defend against hostile same-UID code executing within the authorized process. A monotonic clock is meaningful only within one boot's trusted domain. Future work must define publication acknowledgement/authenticated cross-process transport and failure ordering. No VM/service/ACL/release change.
