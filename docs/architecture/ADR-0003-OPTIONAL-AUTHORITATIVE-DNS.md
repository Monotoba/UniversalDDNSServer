# ADR-0003: Optional first-party authoritative DNS server and backend neutrality

**Status:** Accepted as long-term architectural direction (2026-10-13). Implementation deferred.

## Decision

UniversalDDNSServer will retain a backend-neutral management core. Its first-party authoritative DNS engine will be an **optional separately executable component**, not a dependency of the management core. Existing BIND 9, PowerDNS, other standards-compatible RFC 2136 servers, and supported provider API adapters remain first-class integrations. No first-party capability may be required to operate external backends.

The first-party engine targets understandable configuration, small deployments, low resource consumption, interoperable protocol behavior and modular implementation. An operational DNS service must not require the web UI.

## Separation and contracts

- Management core owns account authentication, record authorization, audit, change requests and update orchestration.
- DNS backend port provides capability discovery, update/observe operations, typed errors and optional conditional-write support.
- The first-party authoritative server owns the DNS listener, zone snapshots, authoritative answer generation, protocol handling and persistence. It communicates with management over a documented, authenticated versioned control interface, not by sharing writable SQLite files.
- Other backend adapters implement the same port, with explicit capability flags. The core must gracefully reject unsupported record types and operations.
- Plugins cannot bypass the core's administrative authorization; DNS request processing itself must have independent protocol and update-policy enforcement.

## First-party engine implementation stages

1. **Experimental**: one primary authoritative zone; UDP/TCP DNS, A/AAAA, SOA, NS and necessary CNAME behavior; class and response-code correctness; bounded parsing and query limits; loopback-only defaults for development.
2. **Useful standalone server**: multiple zones; configurable listeners and TTLs; TXT/MX/PTR/SRV/CAA; safe reload/zone validation; documented systemd deployment; extensive interoperability tests.
3. **Dynamic authoritative backend**: RFC 2136 and TSIG updates with restrictive update policies, atomic RRset mutation and durable persistence; conformance with management interface.
4. **Advanced interoperability**: secondary service, AXFR/IXFR, NOTIFY and DNSSEC only when validated against established implementations. Advanced features are not implied by earlier milestones.

No recursive resolver, general-purpose forwarding resolver, or remote-access tunneling is in scope. Avoid promising production readiness until negative testing, protocol fuzzing, operational safety and security reviews pass.

## Constraints and acceptance criteria

- Prefer a stand-alone minimal runtime with bounded memory and graceful shutdown; **measure** idle memory and sustained query throughput rather than setting unsupported performance claims.
- Config files must be human-readable, schema-validated, and usable without a dashboard.
- Supported DNS formats and protocols should be validated against RFCs and interoperability tests using BIND 9 and at least one independent implementation where feasible.
- Updates must be atomic at RRset scope. DNS replies must never depend on management UI availability.
- Run tests for malformed/truncated packets, TCP framing, compression pointers, negative answers, out-of-zone queries, UDP size limits, shutdown/restart, and concurrency.
- Evaluate implementation language and security architecture independently before writing a network-facing parser. Python for the management core does not dictate the engine language.

## Consequences

Maintaining authoritative DNS creates long-term protocol, security and operational responsibilities. The management core will remain useful even if the first-party engine is experimental or discontinued. A separate repository may be appropriate once implementation starts; share specifications, not internal state or unrestricted privileges.
