# UniversalDDNSServer

[![Status: design phase](https://img.shields.io/badge/status-design%20phase-blue)](docs/IMPLEMENTATION_PLAN.md) [![License: BSD--2--Clause](https://img.shields.io/badge/license-BSD--2--Clause-green)](LICENSE)

**UniversalDDNSServer** is a modular, self-hosted, open-source Dynamic DNS (DDNS) management service. **Design phase only:** no functional server, published binaries, or deployment packages are available yet.

## Goals

- Authenticated updates of IPv4 (A) and IPv6 (AAAA) records for multiple devices.
- Versioned HTTPS API and optional DynDNS2-compatible protocol adapter.
- Replaceable DNS backends, beginning with RFC 2136 using TSIG.
- Lightweight SQLite persistence and independent audit/event interfaces.
- Per-host authorization, idempotent updates, robust error handling, and thorough tests.
- Modular core with stable internal ports and optional extensibility through trusted adapters/plugins.
- Native Linux deployment and optional container packaging.
- Independent integration with [UDDNSUpdater](https://github.com/Monotoba/UDDNSUpdater).

## Architecture

```text
Clients / UDDNSUpdater / Routers
        | HTTPS REST v1 or DynDNS2
        v
   Authentication + Authorization
        |
   Update Orchestrator
   |         |          |
DNS Adapter  State Store  Audit/Events
   |
RFC 2136 / Provider API
   |
Existing authoritative DNS infrastructure
```

DNS providers, persistence, update transports, and notifications interact through **core-owned versioned interfaces**, not implementation-specific dependencies. Third-party plugins are optional and never bypass authorization. The first release uses established DNS infrastructure; it does not implement an authoritative DNS server.

## Design documentation

- [Project proposal](docs/PROJECT_PROPOSAL.md)
- [Design specification](docs/DESIGN_SPEC.md)
- [Implementation roadmap](docs/IMPLEMENTATION_PLAN.md)
- [Architecture](docs/architecture/ARCHITECTURE.md)
- [Threat model](docs/architecture/THREAT_MODEL.md)
- [API](docs/dev/API.md)
- [Internal contracts](docs/dev/INTERFACES.md)
- [Plugin design](docs/dev/PLUGINS.md)
- [Development guide](docs/dev/DEVELOPMENT.md)
- [Testing strategy](docs/dev/TESTING.md)
- [Deployment notes](docs/operations/DEPLOYMENT.md)

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [CHANGELOG.md](CHANGELOG.md).

## License

Copyright (c) 2026 R. Morgan and contributors. Distributed under the [BSD 2-Clause License](LICENSE) (`BSD-2-Clause`). Redistributions must retain the applicable copyright and license notices and disclaimer as set out in the license. No additional advertising requirement is imposed.
