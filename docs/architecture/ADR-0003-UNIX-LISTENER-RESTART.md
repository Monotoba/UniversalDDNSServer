# ADR-0003: Disposable owned Unix endpoint shutdown and restart

PR #144 adds an isolated pathname lifecycle wrapper around the bounded
AF_UNIX listener. It requires an existing 0700 directory owned by the
effective UID, refuses any preexisting socket pathname, and records the
bound socket's device and inode. Graceful shutdown closes accepted peers,
closes the listening descriptor, and removes only its own still-matching
socket inode. Replaced pathname occupants are not unlinked.

A forced termination leaves the pathname behind. This deliberately does
**not** automatically reclaim a stale socket on restart: the coordinator
must separately authenticate and explicitly remove its own disposable
fixture endpoint after confirming the owner terminated. No production
reclamation policy is implied. The test uses SIGKILL only on an isolated
child process, not a real service.

Tests exercise normal shutdown/restart, occupied paths and symlinks,
path replacement, insecure directories, and killed-owner recovery under
the Linux CI matrix. These checks do not defend against an untrusted
same-UID actor able to rename the private directory or replace its
contents concurrently; the production design must also verify ancestor
ownership, trusted runtime directory lifetimes, and service identity.
No deployed service, VM, systemd unit, account, ACL, DNS or live DB changes.
