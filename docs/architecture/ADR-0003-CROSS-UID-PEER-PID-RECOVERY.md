# ADR-0003: Exact cross-UID peer process binding

PR #137 strengthens the disposable Linux cross-UID handoff acceptance tests.
For each negative exchange the privileged coordinator passes the newly forked
sender PID to the observer through a private, one-shot pipe; the observer
requires that precise PID from kernel SO_PEERCRED in addition to the publisher
UID, ownership, inode, expected generation and single-use challenge.
The wrong-PID negative case deliberately supplies a different PID while
retaining the otherwise correct publisher UID and descriptor.

Fresh-session recovery also pins the new sender PID. A test repeating sender
crashes and bad connections must recover only with a newly authorized process
and new session, without reusing the previous PID expectation. The tests run
under the existing privileged Linux integration matrix and do not provision
production identities, sockets, ACLs or services.

SO_PEERCRED binds identity at the socket connection, not ongoing process
health or code integrity. PID reuse, same-UID privilege and maliciously
authorized publishers remain outside this fixture's guarantee.
