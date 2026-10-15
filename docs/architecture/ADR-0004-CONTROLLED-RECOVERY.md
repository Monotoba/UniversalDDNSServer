# ADR-0004: Controlled recovery of ambiguous DNS publications

Status: Proposed (v0.4). This ADR does not authorize an automatic or forced retry.

## Problem

An expired SQLite lease fences journal completion, but cannot prevent a DNS UPDATE already sent by a previous worker from arriving late. A read-only authoritative observation may match or differ while an earlier request is still in flight. Therefore lease expiry and a single observation are insufficient to transition an ambiguous `applying` intent into a safely retryable state.

## Safety invariants

1. Never infer that an old DNS request cannot execute from a lease expiry alone.
2. Never replay ambiguous publication automatically.
3. Never replace an `applying` intent solely because an observation differs or fails.
4. Preserve original intent identity, audit evidence, and idempotency-key history.
5. Journal decisions must be atomic and compare the expected state and ownership generation.
6. DNS-side fencing or an independently verified quiescence protocol is required before releasing a blocked RRset for conflicting writes.
7. Reconciliation must not treat propagation to recursive caches as authoritative confirmation.

## Proposed recovery protocol (not yet implemented)

**Assessment:** obtain journal state, owner token/lease metadata, worker health, and observed authoritative RRset. Do not reveal tokens or TSIG data in CLI/HTTP output.

**Quiescence:** stop intake for the affected RRset; stop relevant publishing workers; verify all workers capable of publishing to this zone are terminated and cannot restart. Network timeouts are insufficient proof if a remote update could remain queued. External writers and secondary authoritative servers must be accounted for.

**Decision:** independently inspect authoritative state and outstanding transport evidence. Only after quiescence is demonstrably established can an operator choose either (a) confirm the already-applied intent, (b) explicitly abandon it while retaining audit history, or (c) create a new separately authorized intent. No transition may modify a live `applying` owner.

**Execution:** require an explicit per-intent operator approval, short-lived action nonce, expected journal generation, and a durable audit record in the same SQLite transaction as any state transition. Require read-back after a permitted transition. Never silently replace stale or conflicting state.

## Key unresolved design questions

- How to prove remote DNS update quiescence across a provider API, rather than only local BIND 9?
- How to fence late writes at the authoritative endpoint, given RFC 2136 prerequisites do not provide exact RRset CAS or a versioned generation field?
- How to address multiple server processes, external writers, and operator authority?
- What is the backward-compatible SQLite schema migration and rollback behavior?
- How will operator attribution, one-time approvals, and tamper-evident audit records work?
- Which failure modes require human escalation rather than a new update?

## Required tests before implementing mutations

- SIGKILL before dispatch, after DNS acceptance, and during journal completion.
- Lease expiry during a blocked transport, followed by a late successful write.
- Two competing operator sessions and compare-and-swap failures.
- Permission revocation after assessment, before approval and execution.
- SQLite restart, WAL persistence, migration and rollback tests.
- Real isolated BIND 9 and fake provider with delayed/out-of-order acknowledgements.
- Assurance that a failed observation or expired lease never triggers a write.

## Current implementation

The v0.4 `assess` command and `reconcile` operate conservatively. `assess` is read-only and emits audit events; `reconcile` only verifies matching DNS state while respecting lease conditions. This document specifies future behavior only and does not change these guarantees.

## v0.4 incremental implementation: journal generation

Each intent now stores a nonnegative SQLite `generation`, initialized to zero in new and migrated journals. Successful claim, lease renewal, completion, verification, or explicit requeue increments it atomically in the existing transaction. `SQLiteIntentJournal.generation(identifier)` exposes this metadata to internal callers. The addition does **not** authorize recovery transitions, ensure that the DNS server fences outstanding writes, or add any operator approval endpoint. Future compare-and-swap transitions must require an expected generation in their `WHERE` condition, enforce worker quiescence independently, and include a durable audit decision. There is currently no force-unblock command.

`SQLiteIntentJournal.require_generation(identifier, expected_generation)` now validates a snapshot and rejects stale values across SQLite connections without changing journal or DNS state. This is **not** a transactional compare-and-swap for a future operation: a separate validation followed by an update is vulnerable to a time-of-check/time-of-use race. Any future state-changing operation must atomically include `WHERE generation = ?` and affected-row checks in its own SQL update, together with the required operator and DNS quiescence safeguards.
