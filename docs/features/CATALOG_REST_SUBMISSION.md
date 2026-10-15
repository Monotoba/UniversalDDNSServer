# REST submission for managed catalog records (v0.4 development)

After an authorized operator creates and stages a catalog A/AAAA record, a client token explicitly scoped to that record ID can submit an IP address using the existing endpoint:

```text
PUT /api/v1/records/{record_id}/address
Authorization: Bearer <token>
{"address":"192.0.2.42","request_id":"unique-request-id"}
```

The HTTP handler uses a fresh validated catalog snapshot for record lookup and keeps the existing requirement for `records:write` plus explicit record-ID scope. The endpoint returns an accepted durable intent (`202`), **not a claim of DNS publication**. Clients can query `GET /api/v1/intents/{intent_id}` with their `intents:read` scope while the record remains active.

The worker independently rechecks current record identity, activation and token grants before DNS publication; a previously queued intent is refused if its record has been deactivated or its authorization revoked. Static configured records retain their existing behavior. The HTTP server itself never calls the DNS backend to publish.

**Known limit:** authorization and DNS publication are not an indivisible operation. Revocation or deactivation after the worker's final check can race a remote DNS write. Only run in the established loopback-only experimental environment. Do not interpret catalog staging as a production-safe DNS fencing protocol; isolated BIND 9 publication tests and deployment qualification are still required.
