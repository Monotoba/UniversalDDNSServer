# ADR-0002: Implementation language and framework

**Status:** Accepted for initial implementation, 2026-10-13.

## Decision
Use **Python 3.11+** for the modular core. Prefer `dataclasses`, `typing.Protocol`, `ipaddress`, `sqlite3` and `unittest` from the standard library. Package with `pyproject.toml` and a `src/` layout. Select **FastAPI/ASGI** for a *future* HTTP transport adapter, not as a domain or persistence dependency; add it only when an endpoint and tests exist.

Implement ports for persistence, DNS publishing, authorization, and events. Inject adapters via constructors rather than importing infrastructure from the domain. Keep the record model RRset-based and backend-neutral. SQLite stores desired state; publication and reconciliation are separate milestones.

## Alternatives
Go offers easy single-binary distribution; Rust offers stronger compile-time guarantees. Both raise the initial contribution/implementation cost relative to the existing Python workflow. Flask is viable but offers less schema-first API support than FastAPI.

## Consequences
Maintain Python security updates; package native and container deployment later. SQLite is initially single-node and cannot prove DNS publication. Add tests for concurrent writers and crash recovery before production use. Interface version negotiation is required for future optional plugins.

## Verification
`PYTHONPATH=src python -m unittest discover -s tests -v`
