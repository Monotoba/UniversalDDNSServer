# Authenticated API-to-DNS pipeline (pre-alpha)

The HTTP API accepts either a static tuple of APIPrincipal or a callable that returns an up-to-date tuple. Configure a callable which opens a **new** SQLite TokenStore connection for each request, rather than sharing a thread-bound connection:

```python
def active_principals():
    with TokenStore(database_path) as store:
        return store.principals()
```

The TokenStore persists hashed random credentials with per-principal scopes and record permissions. Revocation is effective on the next request when using a dynamic principal provider. Issuance and revocation are currently **local administrator operations only**, not HTTP endpoints; restricting access to the database and administrative process is essential.

The PublicationWorker can execute a bounded pass with run_once(), or a supervised, cooperative loop via serve(stop_event, journal_factory, orchestrator_factory). Each loop pass uses a new database connection. The HTTP process itself does not publish DNS. Network calls may outlive a shutdown request until their transport timeout.

Integration tests exercise bearer authentication, HTTP 202 durable queue submission, separate worker publication via signed RFC 2136, authoritative BIND 9 A-record observation, intent status polling, and live token revocation.

Still needed before public exposure: deployment and process supervision, TLS/reverse proxy configuration, durable audited administration, credential rotation, global rate limiting, worker health/readiness, controlled retry policy, and stronger DNS multi-writer semantics. This is **not** a production release.
