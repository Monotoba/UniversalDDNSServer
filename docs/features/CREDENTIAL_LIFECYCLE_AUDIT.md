# Local credential lifecycle audit

The token store now appends a durable, nonsecret `credential_audit` entry in the same SQLite transaction as successful token issuance and successful token revocation (by bearer or by local reference). Repeated attempts to revoke an already-revoked credential do not append another successful revocation event.

Authorized local operators can inspect up to the 100 latest entries with:

```sh
python -m universalddns.admin --config CONFIG history
```

Events include a monotonically increasing event ID, action (`issued` or `revoked`), database-local credential reference, principal and SQLite UTC timestamp. Events omit bearer tokens and digests; they also omit the requesting OS user because this first implementation has no trusted operator attribution for all credential mutations.

Historical credentials issued or revoked before this migration are not reconstructed, and the audit is **not tamper-evident** against SQLite administrators. This change adds no network endpoint and does not authorize DNS publication.
