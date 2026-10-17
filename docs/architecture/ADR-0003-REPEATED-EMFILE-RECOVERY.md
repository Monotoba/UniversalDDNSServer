# ADR-0003: Bounded repeated Linux EMFILE recovery

PR #163 extends the disposable RLIMIT_NOFILE child fixture to perform four sequential cycles of real Linux descriptor exhaustion, fail-closed SCM_RIGHTS reception, resource release, and successful fresh transfer. It checks the reference source FD remains valid and explicitly closes each successful receive descriptor. The parent retains a 15-second timeout.

Each exhaustion phase and its limit changes are confined to the child process; no production host limits are changed. This remains a bounded regression test, not evidence of unbounded durability, systemic ENFILE handling, concurrent FD reuse safety, or complete absence of leaks elsewhere in the process.

After this PR, the next work should prioritize user-facing UniversalDDNSServer features instead of further incremental handoff test-only changes.