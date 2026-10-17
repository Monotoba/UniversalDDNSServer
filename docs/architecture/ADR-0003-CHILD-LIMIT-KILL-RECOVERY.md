# ADR-0003: Isolated child resource caps and forced lock termination

PR #121 adds Linux-only adversarial acceptance fixtures. A child independently
installs RLIMIT_NOFILE, RLIMIT_AS and RLIMIT_CPU constraints, sends an invalid
acknowledgement, and stalls; repeated parent observer attempts must fail
closed, reap their children, avoid descriptor growth, and leave the parent's
own resource limits unchanged. The test uses a disposable SQLite source
and private publication directory.

A separate child acquires the cooperative observer-session flock, is
terminated by SIGKILL, and must release the lock. The parent cannot
infer trusted issuance from lock recovery; only an independently completed
new publication can issue trusted generation state.

These tests do not install RLIMITs in actual publisher or reader services.
Timeouts remain best-effort for work performed outside the bounded pipe
receive and child join, including snapshot inspection and validation.
In particular, this fixture does not establish an end-to-end hard deadline
or a production process sandbox. No broker, VM, systemd, ACL, live source,
DNS, or release modification occurs.
