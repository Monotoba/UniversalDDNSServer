# Verified operator attribution in credential history

The local credential audit now has a nullable `operator` field. The schema migrates existing SQLite databases by adding the column without modifying prior events.

Reference revocation invoked through `python -m universalddns.admin ... revoke-reference` records the username returned by the existing POSIX local-operator group check. This is sourced from the host operating system, not an untrusted `--user` argument. The event is committed atomically with the credential revocation.

Other credential mutations and historical events have `operator: null` because the token store does not have a trusted operator identity for them. **Null means unknown, not that no operator was involved.** This initial change deliberately does not invent attribution or add an HTTP administration route. Token secrets and digests remain excluded from the audit history.

Audits remain locally editable by sufficiently privileged database administrators and are not tamper-evident.
