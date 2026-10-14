#!/usr/bin/env bash
set -Eeuo pipefail
VM="${VM:-uddns-prealpha}"
SIZE_GB=25
RAM_MB=4096
VCPUS=2
CACHE="${HOME}/VMs/${VM}"
STORE="/var/lib/libvirt/images"
DISK="${STORE}/${VM}.qcow2"
SEED="${STORE}/${VM}-seed.iso"
IMG_URL="https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"
die() { echo "ERROR: $*" >&2; exit 1; }
[[ $(uname -m) == x86_64 ]] || die "x86-64 host required"
grep -Eq '(^flags.*\b(vmx|svm)\b)' /proc/cpuinfo || die "KVM support not detected"
for exe in virsh virt-install qemu-img cloud-localds ssh-keygen curl sudo; do command -v "$exe" >/dev/null || die "Missing executable: $exe"; done
virsh -c qemu:///system dominfo "$VM" >/dev/null 2>&1 && die "VM already exists; use virsh start, not this creator"
sudo test ! -e "$DISK" || die "VM disk already exists at $DISK; refusing overwrite"
sudo test ! -e "$SEED" || die "Seed ISO already exists at $SEED; refusing overwrite"
mkdir -p "$CACHE"
[[ $(df -BG "$CACHE" | awk 'NR==2 {gsub(/G/,"",$4);print $4}') -ge 35 ]] || die "Need at least 35 GB free for VM and headroom"
if [[ ! -s "$HOME/.ssh/id_ed25519.pub" ]]; then
  ssh-keygen -t ed25519 -N '' -f "$HOME/.ssh/id_ed25519" -C "$VM" </dev/null
fi
if [[ ! -s "$CACHE/ubuntu-cloud.img" ]]; then
  curl -fL --retry 3 "$IMG_URL" -o "$CACHE/ubuntu-cloud.img.part"
  mv "$CACHE/ubuntu-cloud.img.part" "$CACHE/ubuntu-cloud.img"
fi
TMP_DISK="$CACHE/disk-staging.qcow2"
[[ ! -e "$TMP_DISK" ]] || die "Staging disk already exists; inspect before retrying"
qemu-img convert -f qcow2 -O qcow2 "$CACHE/ubuntu-cloud.img" "$TMP_DISK"
qemu-img resize "$TMP_DISK" "${SIZE_GB}G"
cat > "$CACHE/user-data" <<CLOUD
#cloud-config
users:
  - name: ubuntu
    groups: [adm, sudo]
    shell: /bin/bash
    sudo: 'ALL=(ALL) NOPASSWD:ALL'
    ssh_authorized_keys:
      - $(cat "$HOME/.ssh/id_ed25519.pub")
ssh_pwauth: false
package_update: true
packages: [qemu-guest-agent]
runcmd:
  - [systemctl, enable, --now, qemu-guest-agent]
CLOUD
cat > "$CACHE/meta-data" <<META
instance-id: ${VM}-01
local-hostname: ${VM}
META
cloud-localds "$CACHE/seed-staging.iso" "$CACHE/user-data" "$CACHE/meta-data"
if ! virsh -c qemu:///system net-list --name | grep -Fxq default; then
  virsh -c qemu:///system net-info default >/dev/null || die "libvirt default network missing"
  virsh -c qemu:///system net-start default
fi
sudo install -d -m 0755 "$STORE"
sudo install -m 0600 "$TMP_DISK" "$DISK"
sudo install -m 0644 "$CACHE/seed-staging.iso" "$SEED"
virt-install --connect qemu:///system --name "$VM" --memory "$RAM_MB" --vcpus "$VCPUS" \
  --import --os-variant ubuntu24.04 --network network=default,model=virtio \
  --disk "path=$DISK,format=qcow2,bus=virtio" \
  --disk "path=$SEED,device=cdrom" \
  --graphics none --console pty,target.type=serial --noautoconsole
rm -f "$TMP_DISK" "$CACHE/seed-staging.iso"
echo "VM launched. Run: virsh -c qemu:///system domifaddr $VM --source lease"
echo "For repeated boots use virsh start; never rerun provisioning on an existing disk."
