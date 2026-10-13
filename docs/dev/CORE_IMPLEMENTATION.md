# First implementation milestone: core and SQLite

**Status:** Pre-alpha; no HTTP endpoint, client authentication service, authoritative DNS update, or deployable server yet.

## Runtime choice
Python 3.11+; standard-library domain logic and SQLite persistence. FastAPI is planned for the separate HTTP transport adapter (see ADR-0002).

## Files and responsibilities
- `src/universalddns/domain.py`: immutable A/AAAA RRsets with validated zone/name scope, IP family, TTL, normalization and duplicate detection.
- `src/universalddns/ports.py`: core-owned `typing.Protocol` interfaces for `RecordRepository`, `DNSBackend`, `Authorizer`, and `EventSink`; initial interface version constant.
- `src/universalddns/adapters/sqlite.py`: transactionally stores **desired** RRset state, uses bound SQL parameters, and checks schema version. It does **not** publish DNS.
- `tests/test_domain.py` and `tests/test_sqlite.py`: validation, persistence, no-op, update/delete, schema-version and SQL input regression tests.

## Run
Requires Python 3.11+.

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

For a checkout without an editable install:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Intentional limitations
- Only A and AAAA RRsets accepted. Typed record handlers and RRset-level generalization can be added later.
- No automatic network address discovery, HTTPS API, token issuance, multi-user identity, TSIG backend, job/retry queue or auditing yet.
- `put` is a local desired-state operation, **not** a successfully propagated DNS update.
- SQLite connections belong to individual repository instances; sharing across threads is not supported.
- Schema version checking exists, but there is not yet a general migration framework.
- Further changes must include tests before expanding any public interface.
