# Experimental DynDNS2 compatibility — v0.3 development

Endpoint: `GET /nic/update?hostname=<managed-fqdn>&myip=<literal-ip>`, loopback-only.
Authorization: HTTP Basic with any nonempty username and a server-issued bearer token as password. Username is ignored; the token identifies the principal. Do not expose this endpoint over HTTP outside the local experimental loopback deployment.

Supported initial subset: exactly one configured hostname, an explicit IPv4 or IPv6 address matching the configured record type (A/AAAA), and server-owned record mapping with existing `records:write` scope. The endpoint never writes DNS directly: it enqueues a durable intent for the separately supervised worker.

Responses are plain text terminated by a newline: `badauth` for missing/invalid token or insufficient scope; `nohost` for unauthorized/unmanaged hostname; `notfqdn` for missing/multiple hostname; `dnserr` for invalid IP family or conflicting submission; `badagent` for unsupported query parameters; `911` for accepted-but-not-yet-published intents and rate limiting.

**Important limitation:** Standard DynDNS2 clients expect `good` on a successful publication or `nochg` for an unchanged address. This asynchronous implementation cannot truthfully return those at intake time; its provisional `911` reply may cause backoff/retries, so it is **not yet suitable for general DynDNS2 clients**. Dedicated compatibility tests and client-interoperability work in Issues #4 and #5 must resolve the response/confirmation contract before claiming broadly compatible behavior. The response code `911` is currently a conservative transient indication, not proof of publication.

No implicit source-IP discovery, unauthenticated updates, comma-separated hostnames, or router-specific options. Use the authenticated REST v1 API when a durable queued intent response and status polling are needed.
