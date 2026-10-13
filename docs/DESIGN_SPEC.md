# Design specification

**Status:** Proposed / pre-implementation.

## Component model
- **Transport adapters:** REST v1 initially; optional DynDNS2 compatibility later. Parse/validate and call application ports.
- **Identity and policy:** authenticate credentials, map principals to authorized zone/record/type operations; deny by default.
- **Update orchestrator:** canonicalize requests, evaluate policy, detect no-ops, serialize concurrent updates per record, invoke backend, persist outcome and emit events.
- **DNS provider port:** independently implemented RFC 2136/TSIG adapter initially; additional provider APIs later.
- **Persistence port:** SQLite first, transactional schema migrations and interface-based repository access.
- **Audit/event port:** structured change history with redacted credentials and minimum necessary IP metadata.
- **Observability:** health endpoints, structured logging, optional metrics and notification adapters.

## Architecture constraints
No transport-specific models within domain logic. No direct provider calls from HTTP handlers. No global registry that bypasses DI. Core code must not depend on plugin implementation modules. Modules have documented public interfaces, error categories and lifecycle rules.

## Logical update workflow
1. Validate TLS and request shape, length, hostname and IP family.
2. Authenticate and authorize record, type and requested action.
3. Resolve existing desired state and acquire per-record concurrency control.
4. If no change, produce idempotent response and audit result.
5. Persist update intent in recoverable state.
6. Apply DNS backend update; classify transient/permanent failures.
7. Persist result and event; report accurately (backend accepted is not propagation verified).
8. Reconcile interrupted or ambiguous outcomes safely.

## Data model
Principal, credential hash/metadata, scope, zone, hostname, record type, desired address, update attempt, backend mapping, audit event, schema version. Credentials are stored as non-reversible values where possible. DNS backend secrets require protected storage; never return them through standard read APIs.

## Security
HTTPS, scoped tokens, rate limiting, controlled client-address discovery behind proxies, hostname/zone canonicalization, DNS rebinding and SSRF precautions for configurable provider targets, reliable audit logs, credential rotation and least-privilege TSIG keys.

## Nonfunctional requirements
Safe restart/reconciliation; deterministic idempotency; observability; support Linux/ARM64 and x86-64; documented backup/restore; compatibility tests; no reliance on hosted project services.

## Critical distinctions
Successful provider API response ≠ DNS propagation ≠ reachable remote service. Public DNS, private DNS and VPN integrations are separate trust boundaries.

## Compatibility policy
REST major version in URL; schema evolution should be additive; plugin capability and semantic version checks; migrations tested forward and rollback where feasible. Breaking changes require migration instructions.
