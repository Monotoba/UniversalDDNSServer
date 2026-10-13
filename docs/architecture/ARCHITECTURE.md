# Architecture

A **modular monolith** is the initial deployment unit. Internal boundaries remain strong enough to extract independent services later if justified.

```text
REST v1 / DynDNS2 -> Authentication -> Authorization -> Orchestrator
                                                   |-> State repository
                                                   |-> DNS backend port -> RFC2136 / API adapters
                                                   |-> Audit + event port -> logs / optional webhooks
```

Core-owned ports use explicit request/result DTOs and typed errors. Adapters can be replaced without modifying domain logic. The DI composition root binds implementations. Only request transport controls HTTP semantics; only the DNS adapter deals with provider-specific protocols.

Plugin designs must specify isolation level, configuration validation, startup/shutdown and compatibility policies. Never grant plugin code implicit access to all credentials.
