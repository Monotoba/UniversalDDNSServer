# Disposable systemd operator-broker lifecycle test

**Status:** Manual, opt-in guest test. This is **not** evidence of a passing
systemd integration test until the commands run and their output is recorded.

Use only a **new**, disposable Ubuntu 24.04 libvirt VM. Do not run any of
these commands on `uddns-prealpha`, `uddns-restore-test`, or a production host.
Existing SQLite ACLs and current CLI remain unchanged.

## 1. Create a new guest (libvirt host)

From a fresh checkout of the repository on the **host**:

```bash
bash tests/deployment/create-broker-test-vm.sh --create-disposable uddns-broker-test-01
virsh -c qemu:///system domifaddr uddns-broker-test-01 --source lease
```

The creator provisions a new guest with an `ubuntu` SSH user; it does
**not** install the broker, marker, or systemd units. Confirm the domain
identity and address before using SSH. Avoid attempting an install over a
pre-existing libvirt domain.

## 2. Provision *only* this new guest

SSH as `ubuntu` to **uddns-broker-test-01**. Verify the host identity and
virtualization before proceeding:

```bash
hostname -s
systemd-detect-virt --vm
test -d /run/systemd/system
```

Obtain a checkout of the intended commit on the **guest** (or securely
transfer one); execute the following from its repository root.

```bash
# The marker is restricted to the disposable guest.
printf '%s\n' UNIVERSALDDNS_DISPOSABLE_BROKER_TEST_V1 |
  sudo tee /etc/universalddns-broker-disposable-test >/dev/null
sudo chown root:root /etc/universalddns-broker-disposable-test
sudo chmod 0644 /etc/universalddns-broker-disposable-test

sudo groupadd --system universalddns-operators
sudo useradd --system --user-group --home-dir /var/lib/universalddns \
  --shell /usr/sbin/nologin universalddns
sudo install -d -o root -g root -m 0755 /opt/universalddns
sudo apt-get update
sudo apt-get install -y python3-venv
sudo python3 -m venv /opt/universalddns/venv
sudo /opt/universalddns/venv/bin/python -m pip install .
# Verify imports using the same unprivileged account as the unit.
sudo -u universalddns /opt/universalddns/venv/bin/python -c \
  'import universalddns.operator_broker_service'
```

Use a **non-editable** installation: the service has `ProtectHome=yes`, so
it cannot import an editable source tree under `/home/ubuntu`. These account-creation commands are designed for a *fresh* guest; if an
account/group already exists, **stop and inspect** instead of suppressing
the error. The test service runs only the ping-only Python broker; do not
copy state databases or TSIG credentials into this guest.

## 3. Preflight, run and capture results (guest)

```bash
bash tests/deployment/check-operator-broker-preflight.sh --preflight
bash tests/deployment/test-operator-systemd-lifecycle.sh --run-disposable-lifecycle
sudo systemctl is-active universalddns-operator.socket universalddns-operator.service
test ! -e /run/universalddns/operator.sock
```

The `is-active` command is expected to report inactive and exit nonzero;
it is an *observation*, not a required successful shell command. The
lifecycle script checks unit syntax, socket permissions and cleanup, and
temporarily installs then removes test-specific systemd units. If cleanup
fails, the script deliberately preserves units for investigation; do not
blindly rerun until the cause is understood.

Capture the script's exit status and relevant `journalctl` output,
redacting any secrets before sharing it. Do **not** conclude that ping,
peer authorization, service restart, or systemd socket activation of the
broker *service* have passed: this smoke script checks the socket unit
and its cleanup only.

## 4. Next acceptance gates

In a separately reviewed increment, extend guest tests to cause actual
socket-triggered service activation, confirm authorized `ping`, deny
unauthorized and root identities, exercise restart/failure recovery, and
verify shutdown cleanup. Keep the original direct SQLite ACLs and CLI
until all the security gates in ADR-0003 have been met.

## 5. Observed live-guest results — 2026-10-16

The following results were observed from **operator-provided terminal output**
on newly created `uddns-broker-test-01` (Ubuntu 24.04.5 LTS, KVM,
`192.168.122.20`). They are *manual acceptance evidence*, **not** CI
or a reproducible automated full-service test. The guest checked out
`585c63ee17876dee303c4066405c94bdef5b1b87` at test time.

| Check | Observed outcome |
| --- | --- |
| Guest identity, KVM, systemd running | Pass |
| Disposable admission preflight | Pass |
| Socket unit creation, 0660 mode, secure directory | Pass |
| Socket stop, RemoveOnStop and initial cleanup | Pass |
| Initial activated service with editable install | **Fail**: `ModuleNotFoundError: No module named 'universalddns'` |
| Non-editable package install and import as service user | Pass |
| Authenticated ping as `broker-test-operator` | Pass: protocol version 1, correct kernel identity |
| Socket access by `ubuntu` (nonmember) | Denied by filesystem permissions |
| Root peer ping | Rejected without response |
| Controlled service restart and subsequent ping | Pass |
| Final unit stop, removal, daemon-reload and socket absence | Pass |

The initial failure was due to installing the Python project **editable**
under `/home/ubuntu`: the systemd service's `ProtectHome=yes` hid the
source directory. Replacing it with a regular `pip install .` under the
service venv resolved the import failure. PR #75 updated this runbook.

The final manual cleanup removed the test service/socket units and confirmed
`LoadState=not-found` and absence of the socket path. The disposable VM,
service environment, test accounts and journals were retained. Subsequent
`systemctl reset-failed` reported unloaded units; this was nonfatal after
removal.

### Not established by this run

An unexpected service crash and **automatic** recovery, durable/authenticated
audit events, service resource limits, abusive concurrency/flood behavior,
complete broker mutation authorization and CLI migration were **not tested**.
The broker remains ping-only. No production rollout, SQLite ACL transition,
or new release is authorized on this evidence. Before promoting the broker,
add reproducible guest checks (including audit and failure cases) and verify
the ADR-0003 security gates.


## 6. Subsequent live validation and resource limits

Operator-provided results on 2026-10-16 also confirmed that audit-enabled
commit `5525ff1` delivered all three events to journald:
`operator_ping_succeeded`, `operator_request_rejected`, and
`operator_peer_rejected`. The test secret was absent from the observed
service journal. This does not establish persistence across reboot.

An authorized request following deliberate `SIGKILL` of broker PID 3833
caused systemd socket-triggered activation of a new broker PID 4122, and
its ping succeeded. The service had `NRestarts=0`; this demonstrates
recovery on a subsequent connection, **not** automatic restart without
traffic. The guest and its installed experimental units were retained.

The unit now specifies `MemoryMax=128M`, `TasksMax=16`, and
`LimitNOFILE=256`. These are proposed conservative limits for a
single-process, ping-only service; unit contract CI is not evidence of
live enforcement. Verify them on the disposable VM with `systemctl show`
and a service ping before considering rollout. No mutation operations or
CLI/SQLite ACL migration is authorized.


## 7. Bounded stalled-client observation and concurrent-handler follow-up

The disposable guest ran the sequential broker with four authenticated,
connected clients holding incomplete requests. A subsequent valid ping
completed in **8.01 seconds**, consistent with four serial two-second read
deadlines; a subsequent ping also succeeded. The service remained active,
using 6,017,024 bytes of memory and one task, with the configured
`MemoryMax=134217728` and `TasksMax=16` in effect. This is a small
bounded experiment, **not** sustained-flood or exhaustion validation.

The next implementation uses a maximum of four concurrently executing
handlers. When full, the listener does not accept new sockets; pending
connections remain in the kernel listen backlog rather than an unbounded
application queue. The per-request deadlines, Linux peer authentication,
and payload-free audit events remain unchanged. This change requires a
separate live acceptance run on the disposable guest before promotion.
