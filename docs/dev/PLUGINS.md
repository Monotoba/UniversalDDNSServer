# Plugin and extension specification (draft)

## Principles
Extensions are optional. Core behavior must work with built-in adapters. Public contracts are versioned independently of internal implementation modules.

## Extension points
1. DNS provider adapters.
2. Persistence adapters.
3. Client update protocol adapters.
4. Authentication integrations.
5. Notification/event sinks.
6. Metrics and monitoring exporters.

## Registration
Each plugin provides immutable ID, version, supported interface versions, declared capabilities, dependency metadata, validated configuration schema and startup/shutdown lifecycle. Core decides whether compatibility constraints are met.

## Security
In-process plugins run with application privileges and are **not sandboxed**. Treat as trusted code; pin versions and review provenance. For untrusted third parties favor separate process integration with narrow IPC permissions. Plugins never bypass core authentication or authorization. Secrets are supplied only to adapters requiring them.

## Lifecycle
Discover -> validate manifest/config -> check compatibility -> register port -> initialize -> health check -> start. Unavailable optional plugins must fail closed without disabling core authorization. Shutdown is orderly, bounded and auditable.

## Testing
SDK contract suite checks version negotiation, capability claims, lifecycle errors, timeout handling, input validation, failure isolation and no-privilege-escalation guarantees.
