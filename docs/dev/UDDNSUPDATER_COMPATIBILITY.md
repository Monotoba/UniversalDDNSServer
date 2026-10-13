# UDDNSUpdater interoperability planning

The separate Monotoba/UDDNSUpdater project uses a `DDNSProvider` adapter interface (`providers/ddns_provider.py`) and provider-specific implementations. Its shared HTTP helper currently expects a provider-specific response and supports GET/PUT with narrowly accepted HTTP statuses; the UniversalDDNSServer API instead returns HTTP 202 with a durable `intent_id`, requiring a follow-up status query.

## Integration adapter contract

- Configure an explicit local-server base URL, opaque `record_id`, and scoped bearer token (not the DNS TSIG secret).
- Send `PUT /api/v1/records/{record_id}/address` with an IP address and stable idempotency `request_id`; accept only HTTP 202 and a valid JSON intent ID.
- Poll `GET /api/v1/intents/{intent_id}` with the same token. Treat `pending` and `applying` as incomplete, `applied` as confirmed according to the server journal, and `failed` as needing reconciliation/operator intervention. Do **not** treat HTTP 202 as DNS publication.
- Bound request timeouts and status polling; persist intent/request identifiers across client restarts to prevent ambiguous retries. Do not repeat updates when the prior attempt has an unresolved outcome.
- Initially restrict to explicitly configured loopback test deployments; remote TLS policy and rollout are separate release gates.

No UDDNSUpdater adapter has been implemented in this repository, and no changes were made to the updater. Compatibility is a planned follow-on milestone, not a verified feature.
