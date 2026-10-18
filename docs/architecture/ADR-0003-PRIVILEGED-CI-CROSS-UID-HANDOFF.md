# ADR-0003: Privileged CI proof of publisher/observer separation

PR #133 runs existing disposable cross-UID publisher tests and a new
cross-UID read-only SCM_RIGHTS test using `sudo` in the Linux integration
workflow. Each job uses temporary fixture files; no persistent user, service
account, ACL, socket or VM is provisioned.

The dedicated publisher UID 65533 owns the SQLite snapshot and its 0700
parent directory. An observer UID 65534 cannot open that pathname for
reading or writing. After privilege drop, the observer listens on a private
abstract Unix socket and receives exactly one read-only publisher-owned FD
through an `SCM_RIGHTS` transfer with a single-use challenge, kernel peer
UID verification, generation verification and explicit inode matching.
The observer can inspect the received descriptor without directory access.

The workflow executes these tests explicitly with effective UID 0 before
dropping privileges in child processes. Unlike ordinary unprivileged
unit runs, these invocations should not skip on GitHub-hosted Ubuntu
runners. Evidence of execution must come from the job log, not the overall
workflow's green status alone.

This is still an isolated fixture, not operational user/account policy.
The observer and publisher process IDs are not pinned in this fixture;
Linux kernel UID checking plus the single-use challenge are the defined
identity constraints. Neither root nor a compromised publisher UID is
contained by these permissions. Real production integration requires
a separately authorized decision, account/systemd changes, endpoint
lifecycle policy and a sole-writer threat-model review.
