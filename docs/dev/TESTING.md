# Testing strategy

Automated tests are mandatory for functional code changes.

- **Unit:** parsers, policy decisions, data normalization, idempotency, DTOs, update planning.
- **Contract:** all implementations of DNS, storage, event and protocol ports.
- **Integration:** test RFC 2136 with isolated authoritative DNS and disposable database; verify A/AAAA answers independently.
- **Security:** invalid/revoked tokens, cross-zone/tenant requests, request throttling, malicious hostnames/IPs, secret redaction.
- **Reliability:** provider timeout and 5xx, retry, interrupted update, database locking, simultaneous writers, restore.
- **Compatibility:** documented router/DynDNS2 responses and UDDNSUpdater usage.
- **Docs:** links, example config validation and code sample checks.

CI must not require production DNS, production secrets, or externally reachable customer endpoints. Record test environment versions and publish meaningful results.
