# Durable update intent milestone (pre-alpha)

This milestone introduces `UpdateOrchestrator` and `SQLiteIntentJournal`. The orchestrator enforces an injected authorization policy **before** persisting the intent, checks advertised backend record type support, and delegates publishing through `DNSBackend`.

## Lifecycle

`pending -> applying -> applied | failed`.

- Submitting returns an intent, **not proof of publication**.
- `apply` is designed to be invoked by trusted internal workers, not directly exposed as an unauthenticated public endpoint.
- An SQLite partial unique index permits only one pending/applying intent per RRset.
- Intent creation and transitions are transactional; publishing happens outside database transactions.
- Pending jobs survive restart. Applying jobs remain **ambiguous after process failure** and are exposed by `interrupted()`; they are **not blindly retried**.
- Backend failures are recorded as failed with exception **type only**, to avoid persisting possibly sensitive exception text. A network timeout might still mean the remote backend processed the update.
- Existing desired-state `SQLiteRecordRepository` remains separate; journal completion does not mutate it.

## Important production gaps

- No worker scheduling, startup reconciliation, lease/heartbeat, distributed claim ownership, outbox-to-desired-state atomicity or automatic retry.
- No authoritative DNS backend yet; tests use a fake backend.
- No per-request authentication, token issuance, HTTP endpoints, audit security log or persistence of policy decisions.
- Idempotency for repeated client request IDs and cross-process authorization revocation is not implemented.
- Journal schema migrations and advanced crash consistency tests are still required.
- Avoid using this as a production DDNS server.

## Tests

`python -m unittest discover -s tests -v`

Includes denied submissions, duplicate active intents, successful and failed publish attempts, persistence across reopening, and ambiguous applying-state detection.
