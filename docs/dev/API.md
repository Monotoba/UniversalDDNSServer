# Public API contract (draft)

Base path: `/api/v1`. TLS required for remotely exposed deployments; requests/responses JSON.

## Update address
`PUT /api/v1/records/{record_id}/address`

```json
{"type":"A","address":"203.0.113.42","request_id":"client-generated-unique-id"}
```

`record_id` is a server-mapped identifier; authorization MUST bind record identity, zone, owner and type, rather than trust client-supplied names.

Proposed responses:
- `200` applied/no-op, containing explicit `outcome` and `backend_status`.
- `202` only if an asynchronous durable job is actually queued, with a pollable job ID.
- `400/422` invalid input; `401` unauthenticated; `403` unauthorized; `404` inaccessible/unknown record; `409` conflict; `429` throttled; `503` backend temporarily unavailable.

Server should reject arbitrary public IP spoofing by default or enforce an explicit trusted policy. IPv6 requires AAAA and correct address family. Idempotency keys, error shapes and retry headers must be fully specified before API stabilization.

## Health
`GET /health/live` for process liveness; `GET /health/ready` for dependencies. Avoid credential and private host disclosure.

## Compatibility
DynDNS2-style adapter follows in a later phase, under separate authentication/response mappings. External API versioning and internal adapter API versioning are distinct.
