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
