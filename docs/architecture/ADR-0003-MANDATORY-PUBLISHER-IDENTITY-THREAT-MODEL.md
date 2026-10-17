# ADR-0003: Mandatory publisher identity boundary — threat model

PR #132 adds disposable **root-gated Linux acceptance tests**, without
provisioning any host accounts or changing production filesystem ACLs.

## Authority model

The publisher UID/GID (fixture 65533) owns a private directory (0700),
the live fixture SQLite source (0600), and the published SQLite snapshot
(0600). An independent observer UID/GID (fixture 65534) does not have
directory search, read, rename or write authority. Root creates only
disposable files and changes their ownership. Publisher child processes
are dropped to the dedicated identity with `setgroups([])`, `setgid`
and `setuid`. The observer child is also dropped before attempting
unauthorized writes, renames, publisher API calls, and pathname reads.

Tests demonstrate that publisher-owned files are not mutable or directly
readable to the observer identity even when it deliberately bypasses the
cooperative observer lock. The owner remains able to publish a new
generation. Killing an owner process does not confer write authority
on the observer.

## Limits and next phase

These tests require a privileged Linux test runner and are skipped on
ordinary unprivileged CI. Passing the full CI matrix therefore does not
by itself confirm that the cross-UID assertions executed on every runner.
A non-root runtime will need a **separate authenticated descriptor handoff**
(or tightly designed read-only ACL) to let the observer verify bytes without
giving it directory mutation authority. An unrestricted root process,
publisher-UID compromise, or code with equivalent capabilities is outside
this identity boundary. Other same-UID publisher processes can still
publish; sole publisher instance fencing requires separate control.

Before deployment, provision and audit real service identities, directory
ownership, socket permissions and lifecycle/credential policies on a
disposable VM, separately from this PR. No broker, deployed service,
systemd account, production ACL, live database, DNS or release is changed.
