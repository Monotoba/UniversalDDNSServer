# UniversalDDNSServer

[![Tests](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/docs.yml)
[![Static quality](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/quality.yml/badge.svg?branch=main)](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/quality.yml)
[![BIND 9 + SQLite integration](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/integration.yml/badge.svg?branch=main)](https://github.com/Monotoba/UniversalDDNSServer/actions/workflows/integration.yml)
[![License: BSD-2-Clause](https://img.shields.io/badge/license-BSD--2--Clause-green)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![Status: Pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)](docs/IMPLEMENTATION_PLAN.md)

**Experimental pre-alpha:** Modular self-hostable DDNS management platform. An authenticated FastAPI API and separately supervised publishing worker are available for experimental loopback-only deployments; a production-ready public service is not supplied.

The **current `main` branch contains unreleased v0.4 development features**. The [v0.3.0a1 alpha prerelease](https://github.com/Monotoba/UniversalDDNSServer/releases/tag/v0.3.0a1) is published; see its [release notes](docs/releases/v0.3.0a1.md). Earlier [v0.2.0a1](https://github.com/Monotoba/UniversalDDNSServer/releases/tag/v0.2.0a1) and [v0.1.0a1](https://github.com/Monotoba/UniversalDDNSServer/releases/tag/v0.1.0a1) prereleases remain available.

## Implemented
- Python 3.11+ immutable validated A/AAAA resource-record-set model with order-insensitive RRset comparison.
- Versioned core ports: DNS backends, state repositories, authorization and events.
- SQLite desired-state repository and durable update-intent journal.
- Authorization-gated `UpdateOrchestrator` and state transitions (`pending`, `applying`, `applied`, `failed`).
- RFC 2136/TSIG A/AAAA publishing adapter verified against an isolated BIND 9 authoritative server.
- Durable per-principal idempotency keys, authoritative observation, and explicit recovery/retry operations.
- Authenticated FastAPI record-update intake with scoped tokens, idempotency, and owner-restricted intent status.
- Local API-token administration, JSON configuration loader, systemd examples and host smoke checks.
- Real localhost client/API/worker/BIND 9 integration with UDDNSUpdater.
- Python 3.11–3.13 unit and BIND 9 integration tests, Ruff lint, scoped mypy checks and GitHub Actions.

**Caution:** A queued intent does not mean DNS changed. A backend timeout may have an ambiguous outcome. `applying` intents after a crash require authoritative reconciliation; unattended retries, general multi-writer guarantees, production TLS, distributed rate limiting and validated production deployment are not implemented. Explicit retries require authoritative observation and an operator decision.

## Unreleased v0.4 development features

These features are in the development branch, **not** in the published v0.3.0a1 wheel:

- SQLite catalog for operator-managed A/AAAA record templates, with revision-controlled creation, editing and staging active/inactive.
- Scoped REST record discovery and asynchronous address updates for activated catalog records. Staging does not itself publish DNS.
- Local-only credential issuance for active catalog records and credential inventory with local references; operators can revoke a credential without its bearer token.
- Inactive-record grants do not block unrelated clients; reactivation is refused while unrevoked credentials still reference the record ID.
- Transactional, nonsecret SQLite credential issuance/revocation audit with verified OS operator attribution for CLI credential mutations.

**Security and operational boundary:** The credential management CLI requires a non-root POSIX user authorized through the `universalddns-operators` group. It must also have filesystem/database permissions granted by the host administrator; group membership alone does not grant access to SQLite or protected config files. Public HTTP credential administration and production internet-facing service are **not** supported. See [v0.4 local operator and upgrade guide](docs/operations/V0_4_LOCAL_OPERATOR_UPGRADE.md).

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
- [HTTP API pre-alpha](docs/dev/HTTP_API.md)
- [BIND 9 integration](docs/dev/BIND9_INTEGRATION.md) · [Recovery](docs/dev/RECOVERY.md)
- [Quality gates](docs/dev/QUALITY_AND_CI.md) · [Interfaces](docs/dev/INTERFACES.md) · [Plugins](docs/dev/PLUGINS.md)
- [Isolated Ubuntu VM test kit](tests/deployment/README.md) · [Linux deployment](docs/operations/DEPLOYMENT.md) · [Pre-alpha release checklist](docs/operations/PREALPHA_RELEASE_CHECKLIST.md) · [Draft release notes](docs/operations/PREALPHA_RELEASE_NOTES_DRAFT.md)
- [v0.3 experimental local upgrade and DynDNS2 client configuration](docs/operations/V0_3_LOCAL_UPGRADE.md)
- [v0.4 operator provisioning and experimental upgrade](docs/operations/V0_4_LOCAL_OPERATOR_UPGRADE.md) · [Credential audit](docs/features/CREDENTIAL_LIFECYCLE_AUDIT.md) · [Controlled reactivation](docs/features/CONTROLLED_REACTIVATION.md)
- [Security policy](SECURITY.md) · [Contributing](CONTRIBUTING.md)

## License
Copyright (c) 2026 R. Morgan. [BSD-2-Clause](LICENSE). Preserve copyright, license, and disclaimer notices as required by its terms.
