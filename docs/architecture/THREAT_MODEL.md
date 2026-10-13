# Threat model

## Assets
DNS record control; device/client credentials; backend TSIG keys/API tokens; user identities; event history; host/address metadata.

## Trust boundaries
Unauthenticated internet -> API gateway; reverse proxy -> application; application -> database; application -> authoritative DNS/provider API; core -> third-party plugins; public/private DNS boundary.

## Threats and controls
- Credential theft: scoped tokens, hashed storage where feasible, rotation/revocation, TLS.
- Unauthorized cross-host change: authoritative policy check bound to zone+hostname+type, negative tests.
- Hostname/IP injection: strict canonicalization and typed parsing; reject malformed FQDN and addresses.
- Replay, floods and brute force: limits, jitter where applicable, audit, uniform authentication errors.
- Concurrent updates and partial failures: transactional intents, serialized per-record writes, reconciliation.
- DNS backend compromise: narrowly scoped TSIG/API keys, protected secret configuration.
- Provider/URL SSRF: restrict adapter target configuration, disallow arbitrary client-defined URLs.
- Plugin supply chain: explicit opt-in, version/capability checks, restricted privileges; process isolation for untrusted code.
- Logging sensitive data: structured redaction and retention controls.

Review the model with each new API and adapter. Verification of DNS does not establish device/network reachability.
