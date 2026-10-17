# ADR-0003: Explicit trusted reclamation of preserved AF_UNIX endpoint

PR #148 adds an isolated, opt-in `reclaim_preserved_socket` operation.
The default listener and its `preserve` policy remain unchanged.
The coordinator must obtain the original socket device/inode before shutdown,
prove that the listener is no longer running, and establish exclusive control
of **all pathname writers** before calling with
`writer_exclusion_established=True`. This boolean is an attestation from
the caller, not proof, authorization, a kernel lock or an access-control gate.

The function opens the private directory without following its final symlink,
pins its descriptor, validates path identity, ownership and mode, checks the
socket entry via that descriptor, and refuses a substituted socket, regular
file or symlink. Missing entries are idempotently reported as absent. It
closes the directory descriptor on every path. Tests use disposable fixtures.

**Security limit:** The identity check and unlink are separate syscalls. A
same-UID writer able to replace the pathname between them can still cause
the wrong entry to be removed. A 0700 mode is insufficient protection against
such a writer. A production coordinator needs independently enforced writer
separation, supervised listener liveness, and coordinated lifecycle; this
fixture deliberately does not implement or assert those guarantees. Checking
whether the socket accepts connections does **not** prove the owner is dead.

No live service, accounts, ACLs, runtime directory, BIND, DNS, database or
release is changed by this PR.
