# ADR-0003: Isolated handoff resource boundaries

PR #142 introduces an **opt-in process-local** nonblocking admission
guard for cooperative handoff callers. A single HandoffAdmission instance
allows at most one entering caller; concurrent entries fail closed
immediately. Failures and exceptions release the slot. Other processes
or independently constructed guards are not covered; this is not a global
network listener quota or deployed broker policy.

The parent completion receiver additionally rejects trailing bytes already
queued after a valid 33-byte completion acknowledgement, without allocating
an unbounded response buffer. This is a best-effort instantaneous check:
future bytes may arrive later and no stream transport can prove a sender
will never send more bytes. Existing one-use challenges, monotonic deadline
and peer pidfd checks remain unchanged.

Linux integration tests cover immediately rejected concurrent contenders,
repeated aborted entries, oversized completion responses, repeated
oversized/slow-drip sessions and fresh-session recovery. No production
services, accounts, VM, ACLs, DNS, database or release are modified.
