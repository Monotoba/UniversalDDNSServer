# ADR-0003: Targeted pidfd handoff FD lifecycle assertions

PR #157 replaces the broad process-wide descriptor-count assertion in the
isolated pidfd handoff fixture with verification of the actual SCM_RIGHTS
descriptor observed at the snapshot-read boundary.

The live authorized peer case must receive exactly one descriptor and close it.
The stale/exited peer and unrelated pidfd cases must reject before the
snapshot read boundary and therefore observe no received descriptor there.
The existing SIGKILL-mid-verification fixture (PR #156) separately checks
closure after receipt and before a final verification failure.

These tests avoid equating process-wide FD-count differences with resource
leaks. A closed numeric descriptor can be reused by other code, so immediate
post-call fstat assertions assume the controlled fixture has no concurrent
descriptor-number reuse. A pre-read refusal does not prove every possible
ancillary FD leak within a failed receive path. This PR does not change
runtime code, UID permissions, DNS, services or deployment.
