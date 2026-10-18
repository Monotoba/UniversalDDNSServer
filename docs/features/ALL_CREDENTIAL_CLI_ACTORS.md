# Operator attribution for all local credential mutations

The local credential CLI now requires a verified member of the POSIX `universalddns-operators` group when issuing tokens, revoking a bearer token, or revoking by credential reference. The OS account returned by `local_operator_identity()` is saved in the same SQLite transaction as each successful mutation.

`python -m universalddns.admin --config CONFIG history` displays the audit `operator` value. The lower-level `TokenStore` API remains callable by trusted application code without an OS operator, in which case `operator` stays `null` (unknown). Historical events are not rewritten and there is no HTTP token-administration endpoint. Callers must not supply an arbitrary unverified name; only the CLI performs OS identity verification.

This is a database audit, not a tamper-evident log, and does not prevent a privileged SQLite administrator from altering the records. Operational accounts using the CLI must be appropriately enrolled in the operator group; root and identity-changing sessions are rejected by the existing operator check.
