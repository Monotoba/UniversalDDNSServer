# ADR-0003: Cross-UID generation rollover fails closed

PR #136 expands the privileged cross-UID handoff acceptance fixture with
generation-rollover behavior. The dedicated publisher UID replaces the
snapshot with a fresh SQLite generation. A legitimate read-only descriptor
sent by that UID must be rejected while the observer retains the preceding
trusted generation and inode. Updating the expected generation but retaining
the stale inode also fails. Only a fresh independently observed generation
*and* inode, in a new single-use authenticated SCM_RIGHTS session, succeeds.

The test also checks for parent descriptor-count growth across failures and
recovery. It executes with the existing explicit privileged Linux integration
step on Python 3.11, 3.12, and 3.13. This verifies snapshot identity and
session lifetime across an atomic replacement; it does not assert that a
malicious publisher UID cannot rewrite data or that an authorized observer
can independently establish issuance. There is no production service,
account, ACL, VM, broker, DNS, live database, or release change.
