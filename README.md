# UniversalDDNSServer

[![License: BSD-2-Clause](https://img.shields.io/badge/license-BSD--2--Clause-green)](LICENSE)

**Pre-alpha development:** A modular, self-hostable, open-source Dynamic DNS management platform. **There is no operational DDNS/HTTP server yet.** The repository currently contains a validated A/AAAA record-set model, core adapter interfaces, SQLite desired-state storage, unit tests and architectural documentation.

## Features implemented
- Python 3.11+ domain models: canonical hostname/zone checks, IPv4/IPv6 validation, RRset value normalization, TTL validation.
- Versioned contracts for DNS provider, persistence, authorization and event adapters (`typing.Protocol`).
- SQLite transactional desired-state persistence, get/put/delete, no-op detection and schema-version guard.
- Automated unit tests and GitHub Actions CI matrix.

## Planned
Authenticated HTTPS REST v1 DDNS updates; RFC 2136/TSIG publication; per-record authorization; durable update/outbox tracking; DynDNS2 compatibility; optional adapters/plugins; web management UI; additional DNS record types.

## Development quick start

```sh
git clone https://github.com/Monotoba/UniversalDDNSServer.git
cd UniversalDDNSServer
python -m pip install -e .
python -m unittest discover -s tests -v
```

These commands **install and test the core library**; they do not start a DDNS server. For a dependency-minimal source checkout use `PYTHONPATH=src python -m unittest discover -s tests -v`.

## Documentation
- [Project proposal](docs/PROJECT_PROPOSAL.md)
- [Design specification](docs/DESIGN_SPEC.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [ADR-0001 modular core](docs/architecture/ADR-0001-MODULAR-CORE.md)
- [ADR-0002 language and framework](docs/architecture/ADR-0002-LANGUAGE-FRAMEWORK.md)
- [Current core implementation](docs/dev/CORE_IMPLEMENTATION.md)
- [Interfaces](docs/dev/INTERFACES.md) · [Plugins](docs/dev/PLUGINS.md) · [API draft](docs/dev/API.md)
- [Threat model](docs/architecture/THREAT_MODEL.md) · [Tests](docs/dev/TESTING.md)
- [Contribution guide](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md)

## License
Copyright (c) 2026 R. Morgan. [BSD 2-Clause](LICENSE): preserve applicable copyright, license and disclaimer notices in redistributions; no additional advertising requirement.
