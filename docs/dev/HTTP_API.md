# Authenticated FastAPI intake (pre-alpha)

This opt-in module implements an HTTP intake surface, not a public production server. Install `pip install -e '.[api]'`, then construct the application with `create_app(journal_factory, orchestrator_factory, records, principals)`. Do not use a shared SQLite connection across FastAPI request threads. `records` is a trusted server-side map of opaque record IDs to the correct zone, name, TTL and record type.

Create principals using `APIPrincipal.from_token` with a cryptographically random 32+ character bearer token, scoped permissions (`records:write`, `intents:read`) and allowed record IDs. Only the SHA-256 token digest is kept by the application. Configuration and token provisioning are not yet implemented; do not put raw bearer tokens in source or command-line arguments.

`PUT /api/v1/records/{record_id}/address` accepts JSON `{"address":"192.0.2.20","request_id":"unique-1"}` and returns HTTP 202 with a durable `intent_id` and `status`. It does not call DNS. `GET /api/v1/intents/{intent_id}` requires identity and record ownership. Only `GET /health/live` is unauthenticated. Unauthorized/unknown record and intent IDs return 404 without disclosing record presence.

The rate limit is process-local and not sufficient for multiple workers or internet exposure. Secure ingress TLS, durable token storage/rotation, credential provisioning, trusted client-IP determination, audit retention, secrets protection, global throttling, backend worker scheduling, an admin interface and integration with UDDNSUpdater remain incomplete. **Never expose this pre-alpha app directly to the internet.**
