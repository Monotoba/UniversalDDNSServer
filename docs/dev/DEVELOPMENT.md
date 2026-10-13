# Development guide

UniversalDDNSServer currently implements a Python domain and SQLite desired-state adapter, **not** a live DNS server.

## Setup
Requires Python 3.11+.

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

A dependency-minimal checkout may instead run `PYTHONPATH=src python -m unittest discover -s tests -v`.

## Modular development rules
- Core-owned ports are in `src/universalddns/ports.py`; domain in `domain.py`; infrastructure in `adapters/`.
- No provider-specific or HTTP dependencies inside the domain.
- Preserve existing behavior when refactoring; add unit, contract and regression tests for each change.
- Validate version compatibility before loading optional plugins. Never assume in-process plugins are sandboxed.
- Open focused branches; commit with descriptive messages; update changelog and API docs; require green CI.

Read [core implementation](CORE_IMPLEMENTATION.md), [interfaces](INTERFACES.md), [plugins](PLUGINS.md) and [ADR-0002](../architecture/ADR-0002-LANGUAGE-FRAMEWORK.md).
