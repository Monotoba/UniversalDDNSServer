# ADR-0003: Single-use child acknowledgement challenge

PR #117 binds the isolated parent-created child acknowledgement to a fresh
256-bit invocation challenge delivered as a process argument over the trusted
parent-child creation boundary. The child returns the challenge and generation
only after the existing durable-publication callback. The parent requires an
exact two-element tuple, exact challenge match, clean child exit, no second
queued message, and a matching independently read current-generation snapshot
before its volatile registry issues trust. Failures invalidate the registry.

Tests reject wrong challenge, malformed payload, mismatched generation,
duplicate acknowledgement, failed child, and consecutive distinct challenges.

This is **not** cryptographic authentication of arbitrary senders. Both
endpoints already belong to the parent-created process pair; the child knows
the nonce, and a compromised authorized child could fabricate a matching
tuple. Multiprocessing Pipe uses Python object serialization and must not
be exposed to untrusted arbitrary peers. The challenge is only a
single-invocation correlation/replay guard for this isolated fixture.
No process-independent attestation, mandatory publisher ownership,
restart-persistent trust, or general socket protocol is established.

No broker, VMs, systemd, accounts, production ACLs, live database, DNS,
or release changes.
