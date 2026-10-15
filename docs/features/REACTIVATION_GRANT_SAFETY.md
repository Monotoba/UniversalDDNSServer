# Record reactivation and credential reuse

An inactive catalog record can retain old token grants. Reactivating it without review would restore those tokens' DNS write access. The catalog now rejects **reactivation** (an inactive record at revision 2 or later) if any unrevoked token still contains the record ID, regardless of token scope. The check and activation update occur in the same SQLite transaction.

Operators should use the local-only credential inventory to identify outstanding grants, revoke the old tokens (using the existing token-on-stdin workflow), then stage the record active with the expected revision. Newly issued tokens can be scoped to the active record using the local token administration CLI. Initial activation at revision 1 is unchanged for compatibility.

This does not retroactively revoke tokens on deactivation, and does not fence a DNS request already sent to the authoritative server. No public-DNS production claim is made.
