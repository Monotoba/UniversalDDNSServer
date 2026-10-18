# ADR-0003: Bounded accepted Unix-domain sockets in isolated fixture

PR #143 adds a disposable AF_UNIX stream listener wrapper with a fixed
maximum of accepted connections (default two). On capacity exhaustion the
wrapper accepts and immediately closes the extra socket without retaining
the descriptor. Accepted sockets must be explicitly released or managed
through the context manager; closing the wrapper releases all retained
descriptors. Tests exercise capacity saturation, FD-count stability, a
stalled client, a terminated client, and fresh client recovery.

Limits: this controls **accepted sockets in one process**, not connections
in the kernel listen backlog, pending clients, connection rate, remote
process count, or multi-process service admission. A malicious peer may
continue to occupy a slot until the application enforces timeouts and calls
release. The fixture has no production listener or broker integration,
service accounts, ACL changes, VM deployment or release.
