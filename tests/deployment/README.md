# Isolated Ubuntu VM deployment validation

This is an experimental Ubuntu 24.04 LTS VM fixture for **UniversalDDNSServer**. It is not for production DNS. Requires an x86-64 Ubuntu host with KVM, libvirt, virt-install, cloud-localds, curl and SSH.

## Host setup

```sh
sudo apt update
sudo apt install -y qemu-kvm libvirt-daemon-system libvirt-clients virtinst cloud-image-utils qemu-utils curl openssh-client
sudo systemctl enable --now libvirtd
sudo usermod -aG libvirt,kvm "$USER"
```

Log out and in to refresh group membership. Then:

```sh
bash tests/deployment/create-vm.sh
virsh -c qemu:///system list --all
virsh -c qemu:///system domifaddr uddns-prealpha --source lease
scp tests/deployment/vm-test.sh ubuntu@VM_IP:~/vm-test.sh
ssh ubuntu@VM_IP 'cloud-init status --wait'
ssh ubuntu@VM_IP 'bash ~/vm-test.sh install'
ssh ubuntu@VM_IP 'bash ~/vm-test.sh verify'
ssh ubuntu@VM_IP 'bash ~/vm-test.sh backup'
ssh ubuntu@VM_IP 'bash ~/vm-test.sh restore'
ssh ubuntu@VM_IP 'bash ~/vm-test.sh recovery'
ssh ubuntu@VM_IP 'bash ~/vm-test.sh inflight'
ssh ubuntu@VM_IP 'bash ~/vm-test.sh tsig-deny'
ssh ubuntu@VM_IP 'bash ~/vm-test.sh report'
scp 'ubuntu@VM_IP:uddns-validation-*.tar.gz' .
```

Copy the actual VM_IP from virsh. Reboot using `virsh -c qemu:///system reboot uddns-prealpha`, reconnect, and run `verify` again. To collect evidence of reboot, compare `/proc/sys/kernel/random/boot_id` before and after. Avoid rerunning `create-vm.sh` once a VM is provisioned. To stop/start an existing VM use `virsh shutdown` and `virsh start`.

The launcher stores the cached Ubuntu cloud image in `~/VMs/uddns-prealpha` but installs the *runtime* qcow2 disk and seed ISO under `/var/lib/libvirt/images` to avoid QEMU home-directory access and AppArmor failures. It detects an already active default NAT network. It refuses to overwrite a VM definition or existing runtime disk.

The guest script installs an isolated BIND 9 lab zone (`lab.invalid`), a loopback-only HTTP API, and the publishing worker. Its test results are not proof of production security or public deployment readiness.

**Archive path:** reports are generated in `/home/ubuntu/uddns-validation-TIMESTAMP.tar.gz`, *not* `~/uddns-results/`. Review before sharing; logs can contain sensitive data. The restore test makes a SQLite online backup and restores into a separate scratch database, comparing all table contents to the original; it never replaces the live database. The recovery test stops the worker **before** queuing an update, verifies persisted pending intent and idempotency, restarts the worker, and checks authoritative DNS. It does not cover a crash during an in-flight DNS publication or prove exactly-once transport.

For a VM installed from an earlier checkout, first update the guest repository and copy the new script into the home directory:

```sh
ssh ubuntu@VM_IP 'sudo git -C /opt/universalddns/src pull --ff-only && cp /opt/universalddns/src/tests/deployment/vm-test.sh ~/vm-test.sh'
```

Each mode writes a `*.log.json` with test name, PASS/FAIL and exit code under `~/uddns-results/`. Keep the local token outside Git; inspect report archives before sharing.

The `inflight` test is a **deterministic simulated post-publication timeout** using a disposable SQLite database and fake authoritative backend; it validates reconciliation without a second publish. It is not proof of actual SIGKILL timing, BIND transport exactly-once semantics, or fully offline production database restoration. The `report` command now includes its own final result in the archive.

## Offline installation restoration (destructive to the installed DB file; VM only)

After preserving a VM snapshot or backing up the virtual disk, update the VM checkout and run `bash ~/vm-test.sh offline-restore`. This mode refuses non-VM hosts and hostnames other than `uddns-prealpha`, stops both app services, backs up the stopped SQLite database, restores the same snapshot via an atomic file replacement, verifies data, service-account ownership (`universalddns:universalddns`) and restrictive permissions (`0600`), then starts both services and performs installed-host verification. Failure cleanup attempts to restore the original and restart both services. **Do not run on production systems.** The operator should still retain an independent VM snapshot in case the guest or host crashes during file replacement.

## Restrict TSIG policy on a previously installed VM

The original test fixture permitted A/AAAA updates across the lab zone. The new fixture only permits the `home.lab.invalid.` A record. To migrate an **existing disposable VM** (never a production BIND configuration), run:

```sh
ssh ubuntu@VM_IP 'sudo git -C /opt/universalddns/src pull --ff-only && sudo bash /opt/universalddns/src/tests/deployment/restrict-vm-tsig.sh'
ssh ubuntu@VM_IP 'cp /opt/universalddns/src/tests/deployment/vm-test.sh ~/vm-test.sh && bash ~/vm-test.sh update && bash ~/vm-test.sh verify'
```

The migration refuses unexpected hostnames/configurations, keeps a local backup at `/etc/bind/named.conf.local.prealpha-backup`, validates BIND configuration before reload, and can be safely rerun when the restricted rule is already present. Review that backup as sensitive operational configuration. The `update` test verifies **allowed** publication only; denying another name under the same TSIG key must be separately verified before completing the security checklist.

The `tsig-deny` mode reads the installed lab TSIG key as root, sends a signed update for `disallowed-tsig-probe.lab.invalid.` to the loopback BIND server, asserts an RFC 2136 `REFUSED` response, and verifies the prohibited record remains absent. It first checks the expected VM name and installed lab-zone policy. It never prints the secret.

## One-command update of an existing VM

Use `update-vm.sh` on the **already installed disposable VM**. The updater refuses unexpected hostnames, non-VM systems, dirty checkouts and non-fast-forward source changes. It requires passwordless sudo. It creates a protected, integrity-checked SQLite snapshot after stopping the API and worker; fast-forwards Git; reinstalls the Python distribution without upgrading unrelated dependencies; refreshes systemd units and the test runner; starts both app services; and executes installed-host acceptance checks.

**First run:** copy the updater to the VM outside the source tree, since the updater changes that tree while running. On the Ubuntu host:

```sh
ssh ubuntu@VM_IP 'curl -fsSL https://raw.githubusercontent.com/Monotoba/UniversalDDNSServer/main/tests/deployment/update-vm.sh -o ~/update-vm.sh && bash ~/update-vm.sh'
```

For later runs, `ssh ubuntu@VM_IP 'bash ~/update-vm.sh'` updates to the latest main branch, though fetching the latest updater script first is recommended if it was changed in the meantime.

On a command failure the script attempts to stop both services, restore the prior source commit and Python package, replace SQLite from its snapshot, and restart services. **This is best-effort rollback, not transactional rollback or a substitute for a VM snapshot.** A hard power failure or a change to database schema may require manual recovery. Snapshots persist under `/var/lib/universalddns/upgrade-backup-TIMESTAMP/`; delete old snapshots deliberately, never indiscriminately. The script does not upgrade the OS, BIND 9, or Python dependencies.
