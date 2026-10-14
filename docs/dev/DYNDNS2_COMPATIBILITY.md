# Experimental DynDNS2 compatibility — v0.3 development

Endpoint: `GET /nic/update?hostname=<managed-fqdn>&myip=<literal-ip>`, loopback-only.
Authorization: HTTP Basic with any nonempty username and a server-issued bearer token as password. Username is ignored; the token identifies the principal. Do not expose this endpoint over HTTP outside the local experimental loopback deployment.

Supported initial subset: exactly one configured hostname, an explicit IPv4 or IPv6 address matching the configured record type (A/AAAA), and server-owned record mapping with existing `records:write` scope. The endpoint never writes DNS directly: it enqueues a durable intent for the separately supervised worker.

Responses are plain text terminated by a newline: `badauth` for missing/invalid token or insufficient scope; `nohost` for unauthorized/unmanaged hostname; `notfqdn` for missing/multiple hostname; `dnserr` for invalid IP family or conflicting submission; `badagent` for unsupported query parameters; `nochg <ip>` when an authorized read of authoritative DNS already matches; `good <ip>` only when the independently running worker has persisted an applied outcome; `911` for accepted-but-not-yet-published intents, ambiguous publication failures and rate limiting.

**Important limitation:** Standard DynDNS2 clients expect `good` on confirmed success or `nochg` for an unchanged address. This endpoint waits up to five seconds for a separately supervised worker to record a successful publication, then reports `good <ip>`. If that deadline passes or the result is ambiguous, it returns `911` rather than falsely claiming success. Repeated client retries may enqueue additional updates unless another active update prevents them. Broader client interoperability and router-specific compatibility remain unverified, so this is **not yet suitable for general DynDNS2 clients**. Issue #5 will validate the client interoperability contract. A recorded applied state is not proof of global DNS propagation.

No implicit source-IP discovery, unauthenticated updates, comma-separated hostnames, or router-specific options. Use the authenticated REST v1 API when a durable queued intent response and status polling are needed.
