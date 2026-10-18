# HTTP API reference — experimental v0.4 development

This reference describes the **unreleased current `main` branch**, not the published v0.3.0a1 package. The API is experimental and must remain bound to loopback on a disposable lab installation. There is no production TLS ingress, distributed rate limiter, public credential administration, or production deployment approval.

## Server architecture and authentication

The FastAPI application is constructed by `create_app(journal_factory, orchestrator_factory, records, principals, record_reader=...)`. The runtime can provide a fresh, validated catalog record reader. DNS writes are performed by a separate worker, **not** in the REST request handler. Only server-owned record IDs/RRsets are eligible. Dynamic catalog entries must be staged active first. The compatible DynDNS2 path uses only the static `records` argument.

Except for `GET /health/live`, the REST routes require `Authorization: Bearer TOKEN`. A stored SHA-256 digest is used for authentication; do not log or embed the bearer token in source. Scope names are `records:write` and `intents:read`; a token also grants an explicit set of record IDs. For credential issuance, inventory, revocation and operator authorization, see [v0.4 local operator guide](../operations/V0_4_LOCAL_OPERATOR_UPGRADE.md). There are **no HTTP token-management endpoints**.

The fixed-window rate limiter defaults to 60 authenticated requests per principal per 60-second window **per process**, and is not suitable for distributed production deployment. An unauthorized token returns HTTP 401 and a Bearer challenge; an authenticated principal without the required scope gets HTTP 403; requests over the process-local limit return HTTP 429 with `Retry-After: 60`.

## Route reference

| Method and route | Required scope | Behavior |
|---|---|---|
| `GET /health/live` | None | Returns `{"status":"live"}`; process liveness only, not DNS health |
| `GET /api/v1/records` | `intents:read` | Lists active records explicitly granted to the bearer token, sorted by record ID |
| `PUT /api/v1/records/{record_id}/address` | `records:write` | Validates an A/AAAA address and submits a durable update intent; HTTP 202 is **not** DNS confirmation |
| `GET /api/v1/intents/{intent_id}` | `intents:read` | Returns current state only for the owning principal and an authorized active record with the matching RRset key |
| `GET /nic/update` | Basic password as API token; `records:write` | Experimental DynDNS2 subset for **static configured records only**, plain-text responses |

### Discover authorized records

```http
GET /api/v1/records HTTP/1.1
Authorization: Bearer TOKEN
```

Successful response:

```json
{"records":[{"id":"home","name":"home.lab.invalid.","type":"A","ttl":60}]}
```

The response omits current DNS addresses and records not explicitly granted. If none of the caller's granted record IDs are active, the result can be `{"records":[]}`. Catalog conflicts or invalid snapshot state can return HTTP 503 (`catalog view unavailable`); a deactivated record's dormant grant does **not** by itself invalidate unrelated records.

### Submit an address update

```http
PUT /api/v1/records/home/address HTTP/1.1
Authorization: Bearer TOKEN
Content-Type: application/json

{"address":"192.0.2.20","request_id":"request-001"}
```

Example accepted response (identifier is server-generated):

```json
{"intent_id":"<server-generated-intent-id>","status":"pending"}
```

`address` is a string between 3 and 45 characters and must be a valid IP address for the record type (`A` → IPv4; `AAAA` → IPv6). `request_id` is required, 1–128 ASCII letters, digits, periods, underscores or hyphens. Unrecognized JSON fields are rejected. The request identifier supports durable per-principal idempotency, subject to update-conflict checking. The endpoint enqueues an intent for subsequent worker processing; do not retry ambiguous updates blindly.

Possible application errors include:
- 401: absent/invalid bearer.
- 403: token lacks `records:write` or publication authorization.
- 404: record ID is not explicitly granted, unknown or inactive.
- 409: conflicting submission (including incompatible idempotent reuse).
- 422: invalid request ID, address, body fields or update.
- 429: per-process rate limit exceeded.
- 503: active record catalog snapshot unavailable.

### Inspect an intent

```http
GET /api/v1/intents/INTENT_ID HTTP/1.1
Authorization: Bearer TOKEN
```

A successful response contains `intent_id` and a `status` such as `pending`, `applying`, `applied` or `failed`. HTTP 404 masks nonexistent intents, intents owned by another principal, and intents whose RRset no longer matches an authorized active record. Deactivating a record may make that record's prior intents inaccessible through this API; the local operator can still inspect journal state. HTTP 503 means the current record mapping could not be validated.

**Interpretation:** `pending` or `applying` is not a completed DNS change. An interrupted or timed-out RFC 2136 operation can have an ambiguous external outcome; authoritative DNS observation and operator reconciliation may be necessary.

## DynDNS2 compatibility: `GET /nic/update`

The client sends `Authorization: Basic` with a username and the **API bearer token as the password**, plus `hostname` and `myip` query parameters. The Basic username is ignored. Only a single static configured RRset whose hostname and token grants match is eligible; this compatibility handler does not consume the catalog-active record reader.

Responses are `text/plain` with one newline-terminated token:

| Text | Meaning |
|---|---|
| `good IP` | The worker reported `applied` during the bounded confirmation window |
| `nochg IP` | Backend observation indicates the address is already current |
| `badauth` | Missing/invalid bearer or publication authorization |
| `nohost` | No uniquely matching, authorized static record |
| `notfqdn` | Missing, malformed or multi-host name |
| `dnserr` | Invalid IP address or record-type family |
| `badagent` | Unsupported query parameters |
| `911` | Rate limit, conflict, backend error, failed intent or unconfirmed publication |

The default confirmation wait is five seconds (`dyndns_wait_seconds`, configurable from 0 to 30 seconds at application creation). `911` is **not proof that DNS is unchanged**; inspect the intent and authoritative server before retries. DynDNS2 Basic credentials must never traverse an unencrypted external network; the lab listener is intentionally loopback-only.

## Operational limitations and source of truth

- There is no public credential issuance, revocation, record staging or recovery administration API; those operations are local.
- Catalog and bearer grants are loaded from the SQLite-backed runtime; records must be active and explicitly granted for REST access. Revoking a token or deactivating a record blocks future authorization checks but cannot cancel an RFC 2136 request already sent.
- A credential may reference an inactive record without blocking other clients; deliberate reactivation requires revocation of all outstanding tokens granting that record ID before staging active.
- The process-local limiter, loopback HTTP transport and current audit controls are not a substitute for a hardened production security boundary.
- This reference documents implementation behavior and does not claim a complete formal OpenAPI stability guarantee.

Related: [Local deployment](../operations/DEPLOYMENT.md), [v0.4 operator/upgrade guide](../operations/V0_4_LOCAL_OPERATOR_UPGRADE.md), [controlled reactivation](../features/CONTROLLED_REACTIVATION.md), [BIND 9 integration](BIND9_INTEGRATION.md), and [recovery procedure](RECOVERY.md).
