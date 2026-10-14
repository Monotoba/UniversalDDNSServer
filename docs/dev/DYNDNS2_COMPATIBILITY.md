# Experimental DynDNS2 compatibility — v0.3 development

Endpoint: `GET /nic/update?hostname=<managed-fqdn>&myip=<literal-ip>`, loopback-only.
Authorization: HTTP Basic with any nonempty username and a server-issued bearer token as password. Username is ignored; the token identifies the principal. Do not expose this endpoint over HTTP outside the local experimental loopback deployment.

Supported initial subset: exactly one configured hostname, an explicit IPv4 or IPv6 address matching the configured record type (A/AAAA), and server-owned record mapping with existing `records:write` scope. The endpoint never writes DNS directly: it enqueues a durable intent for the separately supervised worker.

Responses are plain text terminated by a newline: `badauth` for missing/invalid token or insufficient scope; `nohost` for unauthorized/unmanaged hostname; `notfqdn` for missing/multiple hostname; `dnserr` for invalid IP family or conflicting submission; `badagent` for unsupported query parameters; `nochg <ip>` when an authorized read of authoritative DNS already matches; `good <ip>` only when the independently running worker has persisted an applied outcome; `911` for accepted-but-not-yet-published intents, ambiguous publication failures and rate limiting.

**Important limitation:** Standard DynDNS2 clients expect `good` on confirmed success or `nochg` for an unchanged address. This endpoint waits up to five seconds for a separately supervised worker to record a successful publication, then reports `good <ip>`. If that deadline passes or the result is ambiguous, it returns `911` rather than falsely claiming success. Repeated client retries may enqueue additional updates unless another active update prevents them. Broader client interoperability and router-specific compatibility remain unverified, so this is **not yet suitable for general DynDNS2 clients**. Issue #5 will validate the client interoperability contract. A recorded applied state is not proof of global DNS propagation.

No implicit source-IP discovery, unauthenticated updates, comma-separated hostnames, or router-specific options. Use the authenticated REST v1 API when a durable queued intent response and status polling are needed.

## UDDNSUpdater adapter interoperability

The `Monotoba/UDDNSUpdater` repository now includes `UniversalDDNSDynDNS2` alongside the existing, intent-aware `UniversalDDNSServer` REST adapter. CI pins the client revision in `.github/workflows/integration.yml` and exercises the new adapter against the live loopback HTTP API, separate worker and isolated BIND 9.

Experimental client config fields: `base_url=http://127.0.0.1:8765`, `hostname=<authorized-managed-fqdn>`, and `token=<issued-api-token>`. Keep a persistent state file enabled in UDDNSUpdater and protect credentials. The DynDNS2 client accepts only exact `good <ip>` or `nochg <ip>` success, and stops conservatively on `911` or other replies. It never treats an unconfirmed publication as completed; a human operator must inspect ambiguous attempts. The original REST adapter remains preferable when intent identifiers and state polling are required. Neither adapter should be exposed directly over public HTTP.
