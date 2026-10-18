# ADR-0003: Declared inherited socket-holder pidfd exit gate

PR #151 extends the opt-in pidfd reclamation API with
`additional_holder_pidfds=((pid, pinned_pidfd), ...)`.
Each declared descriptor-holder process must have exited before cleanup.
An inherited socket descriptor may keep a listener alive after its original
parent exits; observing only that parent's pidfd is insufficient.

Linux fork-based disposable tests hold the actual listener descriptor open in
a surviving child and establish deterministic readiness through a pipe. They
verify refusal while the child lives, cleanup only after its pinned pidfd
indicates exit, and fail-closed rejection of mismatched or malformed entries.

**Limits:** An external supervisor must accurately enumerate all socket
descriptor holders and pin their pidfds while alive. Unknown holders, FDs
transferred via SCM_RIGHTS, ancestors, and concurrent inheritance are not
discovered by this API. It does not prove socket-to-process identity, verify
exclusion of malicious pathname writers, or make stat/unlink atomic. The
`writer_exclusion_established` flag is still an unverified caller assertion.
No production service or process supervisor is connected.
