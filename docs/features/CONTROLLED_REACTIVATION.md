# Controlled reactivation after catalog deactivation

An inactive catalog record is not eligible for REST updates, and outstanding grants do not affect unrelated records. **Reactivation is now refused while any non-revoked API token still grants the record ID.** This prevents a dormant token from silently regaining control over a record when it is staged active again.

To reactivate, first inspect local credential metadata using `python -m universalddns.admin --config CONFIG list`. Revoke each affected token using the existing local credential revocation command; then stage the record active with its current revision. Any multi-record token containing the reactivated ID must be revoked in its entirety and reissued with only the intended grants. Revoked tokens cannot authenticate.

The activation check occurs under an SQLite immediate transaction, coordinating with concurrent token-table writes. Record activation does not publish DNS or cancel an RFC 2136 write that already left the worker.

**Operational consideration:** The rule also refuses initial activation when a legacy or manually provisioned non-revoked token already names that ID. Revoke stale grants and reissue tokens after activation.
