# Development quality gates

## Local setup

```sh
python -m pip install -e '.[dev]'
ruff check .
mypy
python -m unittest discover -s tests -v
python -m unittest discover -s tests/integration -p 'test_*.py' -v
```

## Automated workflows

- `docs.yml`: unit and documentation tests across Python 3.11, 3.12, 3.13.
- `quality.yml`: Ruff critical-error lint rules and mypy for typed domain + port modules.
- `integration.yml`: stateful workflow using a real SQLite database and fake publishing port.

Ruff intentionally starts with `E4,E7,E9,F` so that pre-existing formatting is not overhauled. Tighten lint coverage incrementally with focused changes and tests. Mypy is **not yet whole-project static typing**; expand module coverage as interfaces acquire complete annotations. No coverage percentage is claimed yet.

The integration workflow **does not exercise a real authoritative DNS server**. RFC 2136/TSIG live integration requires a separate, isolated BIND or PowerDNS job with ephemeral credentials, DNS query verification, and negative tests. Do not use live DNS zones or secrets in CI.

Before branch protection, verify all workflows pass on `main`. Then use the workflow job names as required status checks.
