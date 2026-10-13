# ADR-0001: Modular monolith and replaceable adapters

**Status:** Accepted for initial design, 2026-10-13.

## Decision
Ship one readily operated process with separable transport, authentication, policy, orchestration, persistence, DNS publishing, auditing and observability modules. Define stable ports and use dependency injection. Make external-provider and protocol adapters independently testable.

## Why
A microservice deployment adds complexity to small self-hosted installations. A monolith without contracts obstructs contributions and backend flexibility. A modular monolith offers a simpler operator experience while preserving interface ownership and extensibility.

## Consequences
Enforce dependency direction and contract conformance tests. In-process plugins are trusted code, not a sandbox. Reevaluate deployment topology only if demonstrated workloads require it.
