# Local credential revocation without the original bearer token

An OS-authorized local operator can list credentials blocking a record's reactivation:

```sh
python -m universalddns.record_admin --config CONFIG blockers RECORD_ID
```

Each blocking credential includes a **nonsecret, database-local reference** such as `cred-7`, along with its principal and scopes. The reference is a SQLite row identifier; it is not a bearer secret or token digest. It is not guaranteed to survive database reconstruction, export/import, VACUUM, or arbitrary table rewrites. Obtain a fresh reference immediately before revocation, preferably while other administrative changes are paused.

To revoke a specific credential that is no longer available as a bearer token, use:

```sh
python -m universalddns.admin --config CONFIG revoke-reference --reference cred-7
```

This operation requires the configured OS-local operator identity, immediately revokes one credential, and cannot be invoked through the HTTP API. A token with several record grants loses **all** of its grants when revoked. Reissue replacement credentials as needed.

**Security boundary:** Keep administrative access to SQLite and OS operator roles restricted. A reference is an administrative selector, not proof of user authorization, and must never be accepted by the public API.
