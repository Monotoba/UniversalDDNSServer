# ADR-0003: Observer end-to-end deadline checkpoints

PR #122 extends the *isolated* parent-controlled observer's monotonic
deadline from before child startup through read/verification and successful
return. Late acknowledgements, child exits, initial snapshot reads, and final
current-generation validation now fail closed. An exception invalidates the
volatile registry, even if issuance occurred just before a late final read.

These checks are **not hard wall-clock deadlines**. A blocking SQLite
inspection, operating system call, scheduling delay, or callback can run past
the deadline before the next checkpoint evaluates it. Killing a separate
supervised validation process would be necessary to provide a hard bound,
subject to process-start and termination limitations. The producer's own
backup deadline also remains a separate policy.

Deterministic fixture delays cover expiration during the first snapshot read
and during validation after issuance, plus normal recovery. No broker, VM,
systemd, production ACL, live database, DNS publishing or release is changed.
