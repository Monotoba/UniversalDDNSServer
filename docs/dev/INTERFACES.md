# Internal interfaces (draft)

All interfaces are core-owned and implementation independent. Illustrative shapes, not frozen code signatures.

```text
Authenticator.authenticate(Credentials) -> Principal | AuthError
Policy.authorize(Principal, Record, Action) -> Decision
RecordRepository.get(id) -> Record | NotFound
RecordRepository.reserve_update(record, desired, request_id) -> Intent
DNSBackend.apply(UpdateIntent) -> BackendResult | BackendError
RecordRepository.complete(intent, result) -> StoredResult
EventSink.emit(DomainEvent) -> DeliveryResult
```

Each port must document typed errors, sync/async behavior, transactional expectations, cancellation and idempotency. Backends must never decide which principal may update a hostname; this is a core policy responsibility.

Every adapter runs a shared conformance suite (success, idempotent update, malformed input, transient error, retries, and privilege failures). No plugin may mutate the central policy store directly.
