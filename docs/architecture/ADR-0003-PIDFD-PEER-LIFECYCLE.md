# ADR-0003: Optional pidfd peer-lifecycle verification

PR #138 adds an opt-in Linux pidfd guard to the isolated verified SCM_RIGHTS
descriptor reader. The parent must open a pidfd for the expected sender
*while it is alive*, independently authorize that PID and retain ownership
of the pidfd. The receiver compares the peer's kernel SO_PEERCRED PID,
validates the pidfd's kernel /proc/self/fdinfo Pid field and polls the
pidfd for an exited process before and after pinned SQLite verification.
A failed check consumes the handoff session and closes a descriptor already
received. The caller retains and closes its own pidfd.

The regression fixture launches a genuine separate sender process. It
accepts a live sender; rejects queued SCM_RIGHTS rights if the sender
has already exited, even though SO_PEERCRED records the original PID;
and rejects a live pidfd belonging to the wrong process. The tests run
explicitly in the Linux CI integration matrix.

This is *not* an atomic lifetime guarantee: the sender may exit after
the final pidfd poll, and no check establishes code integrity, generation
issuance, or authorization for arbitrary peers. The check is Linux-specific
and relies on the Linux procfs pidfd identity representation. No production
service wiring, accounts, permissions, DNS, VM, or releases are changed.
