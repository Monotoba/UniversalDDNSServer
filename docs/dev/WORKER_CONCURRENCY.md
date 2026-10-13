# Worker claims and conditional DNS operations

## Implemented

- SQLite `claim_owned()` returns a random worker claim token.
- `finish_owned()` checks the token and applying state atomically. A stale worker cannot record a successful completion after a requeue and reclaim.
- The orchestrator uses token-based ownership for new applications.
- RFC 2136 `publish_if_absent()` uses an authoritative-server-enforced RRset-absence prerequisite, preventing accidental overwrites for new records.
- CI tests include multiple SQLite connections, stale completion rejection, and create-only DNS updates against isolated BIND 9.

## Important limitations

**This is not a complete concurrent-safe recovery worker.** The existing legacy `claim()` and `finish()` compatibility methods are still available to existing callers and are not fenced. There is no durable lease expiry, worker-heartbeat mechanism, automatic restart recovery scheduler, or generic compare-and-swap for existing RRsets. The ordinary `publish()` method continues to perform unconditional replacement, and explicit retry must not be treated as safe in the presence of independent writers. The `supports_prerequisites` capability identifies support for a prerequisite operation, not full compare-and-swap semantics.

Do not expose these primitives directly through an internet-facing API. Subsequent work must implement safely coordinated retry ownership, identity and policy, atomic update prerequisites for changes to existing RRsets, and failure-injection tests.
