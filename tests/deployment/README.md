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
