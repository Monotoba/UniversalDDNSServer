# ADR-0003: Repeated acknowledgement failure lifecycle acceptance

PR #120 extends the isolated acknowledgement observer's regression suite with
Linux procfs-based resource accounting. Six consecutive interrupted,
partial-body publication attempts must leave no extra child processes, no
increase in the parent process's open descriptor count, and no trusted issuance.
A subsequent valid publication must recover. The fixture also injects
`KeyboardInterrupt` in the parent receive path after previous trusted
issuance, asserting that `finally` kills/reaps the child, closes the parent
and child pipe endpoints, revokes issuance and permits recovery.

These checks test existing cleanup behavior and make no changes to deployed
permissions or services. They do not assert precise global process/FD counts,
production watchdog semantics, crash consistency across full host shutdown,
or authenticated arbitrary peer IPC. They use process-relative FD counts and
active multiprocessing-child PID sets in isolated disposable directories.
No broker, VM, systemd service, production ACL, live database, DNS
publication or release is changed.
