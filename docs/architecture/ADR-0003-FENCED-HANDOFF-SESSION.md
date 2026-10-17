# ADR-0003: Cooperative session fencing across the verified handoff chain

PR #131 allows the isolated `publish_in_observer_session` wrapper to opt into
`descriptor_handoff=True`. The existing persistent observer-session flock
then spans the authorized publisher child, publication acknowledgement,
cross-process session-bound SCM_RIGHTS descriptor verification and parent
issuance. Tests prove that another cooperative observer cannot enter
concurrently, a killed observer lock holder releases its flock, and a new
verified full-chain publication can recover.

**This is still cooperative, not mandatory publisher ownership.** A second
same-UID process can call `publish_inventory_snapshot` directly while the
observer session is held. A negative acceptance test deliberately confirms
that bypass. Consequently, this change MUST NOT be interpreted as preventing
unauthorized direct publication, authorizing issuance from an arbitrary
process, or eliminating the post-verification replacement race. A mandatory
writer boundary will require enforcing a dedicated process identity and
filesystem/IPC permissions, not merely another flock. The production broker,
VMs, systemd, live databases, ACLs, DNS and releases remain untouched.
