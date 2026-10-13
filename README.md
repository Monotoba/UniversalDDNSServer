# UniversalDDNSServer

[![Tests](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/docs.yml)
[![Static quality](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/quality.yml/badge.svg?branch=main)](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/quality.yml)
[![BIND 9 + SQLite integration](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/integration.yml/badge.svg?branch=main)](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/integration.yml)
[![License: BSD-2-Clause](https://img.shields.io/badge/license-BSD--2--Clause-green)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![Status: Pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)](docs/IMPLEMENTATION_PLAN.md)

**Pre-alpha:** Modular open-source, self-hostable DDNS management platform. **There is no operational DDNS/HTTP server yet.**

## Implemented
- Python 3.11+ immutable validated A/AAAA resource-record-set model with order-insensitive RRset comparison.
- Versioned core ports: DNS backends, state repositories, authorization and events.
- SQLite desired-state repository and durable update-intent journal.
- Authorization-gated `UpdateOrchestrator` and state transitions (`pending`, `applying`, `applied`, `failed`).
- RFC 2136/TSIG A/AAAA publishing adapter verified against an isolated BIND 9 authoritative server.\n- Durable per-principal idempotency keys, authoritative observation, and explicit recovery/retry operations.
- Unit tests, SQLite workflow integration, Ruff lint, scoped mypy checks and GitHub Actions.

**Caution:** A queued intent does not mean DNS changed. A backend timeout may have an ambiguous outcome. `applying` intents after a crash require manual reconciliation; unattended retries, multi-writer guarantees, client authentication, an operational DNS publishing worker, HTTPS API and production deployment are not implemented. Explicit retries require authoritative observation and an operator decision.

## Test the core

```sh
git clone https://github.com/Monotoba/UniversalDDNSServer.git
cd UniversalDDNSServer
python -m pip install -e '.[dev]'
ruff check .
mypy
python -m unittest discover -s tests -v
python -m unittest discover -s tests/integration -p 'test_*.py' -v
```

## Documentation
- [Project proposal](docs/PROJECT_PROPOSAL.md) · [Design specification](docs/DESIGN_SPEC.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md) · [Changelog](CHANGELOG.md)
- [ADR-0002 language/framework](docs/architecture/ADR-0002-LANGUAGE-FRAMEWORK.md)
- [Core implementation](docs/dev/CORE_IMPLEMENTATION.md) · [Update intent milestone](docs/dev/UPDATE_ORCHESTRATION.md)
- [BIND 9 integration](docs/dev/BIND9_INTEGRATION.md) · [Recovery](docs/dev/RECOVERY.md)\n- [Quality gates](docs/dev/QUALITY_AND_CI.md) · [Interfaces](docs/dev/INTERFACES.md) · [Plugins](docs/dev/PLUGINS.md)
- [Security policy](SECURITY.md) · [Contributing](CONTRIBUTING.md)

## License
Copyright (c) 2026 R. Morgan. [BSD-2-Clause](LICENSE). Preserve copyright, license, and disclaimer notices as required by its terms.
