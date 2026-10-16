# Complete local credential inventory with revocation selectors

`python -m universalddns.admin --config CONFIG list` now prints a database-local `reference` for **every** stored credential, alongside principal, scopes, granted record IDs and revoked status. This complements `record_admin blockers RECORD_ID` when the operator needs to inspect credentials regardless of their record grants.

The list reveals neither bearer tokens nor SHA-256 token digests. An authorized local operator can pass a listed `cred-N` to `admin revoke-reference --reference cred-N` to revoke that one credential, including if the original token was lost. Revocation permanently removes *all* its grants.

References are local SQLite row identifiers, not durable public IDs: after database reconstruction or importing into another SQLite database, fetch a fresh inventory before using them. Never accept references through public HTTP endpoints.
