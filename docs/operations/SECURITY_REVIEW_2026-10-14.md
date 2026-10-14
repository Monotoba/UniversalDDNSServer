# Pre-alpha security review — 2026-10-14

Scope: local Ubuntu VM deployment and tracked configuration. This is a review, **not** a security certification, penetration test or approval for public exposure.

## Verified by configuration and VM evidence

- API unit binds the service to `127.0.0.1:8765`, with a single Uvicorn worker and access logging disabled. Do not put it behind public port-forwarding without a separate, fully reviewed security architecture.
- API and publication worker are run as dedicated `universalddns` user, with `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, restricted writable state path and `UMask=0077`.
- Runtime rejects TSIG credential files with group/other access, rejects database and credential symlinks, and validates configured fields. Offline restore verifies database `0600` and service-account ownership.
- Authentication and denial of unauthenticated intent queries were exercised on the VM; service-account access to SQLite and credential file was checked.
- TSIG policy is enforced **by the authoritative DNS server**, not by the HTTP service. The VM fixture was narrowed from zone-subtree-wide grants to a grant for `home.lab.invalid. A`. The prior installed VM still has its original policy until explicitly migrated.
- The existing VM named server is bound to localhost and configured nonrecursive; the fixture has intentionally limited scope and uses `lab.invalid`.

## Risks and outstanding work

- Existing deployed VM's authoritative TSIG policy has not yet been revalidated after the source fixture change; this is a **required live check**, not a completed gate.
- No production-grade HTTPS termination, external authentication gateway, distributed rate limiting or production firewall rules. Loopback binding is necessary but not sufficient for overall host security.
- Secret rotation procedure, audited retention, backup encryption and automated credential revocation incident response remain immature.
- Actual in-flight worker SIGKILL / partial RFC 2136 write transport failure is not tested. Simulated post-publication timeouts demonstrate observational reconciliation, not exactly-once guarantees.
- Review dependency security advisories and pinning before any internet-facing or production deployment; package dependencies use bounded version ranges rather than hashes.
- Systemd service protections have not been fuzzed or audited against a real-world threat model.

## Release condition

Release as an experimental pre-alpha only, with all above limitations disclosed. No approval is implied for external deployment.
