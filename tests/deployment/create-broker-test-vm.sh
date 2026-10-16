#!/usr/bin/env bash
# Only creates a NEW, explicitly named disposable broker VM.
set -Eeuo pipefail
die() { printf 'REFUSED: %s\n' "$*" >&2; exit 2; }
[[ $# -eq 2 && $1 == --create-disposable ]] ||
  die "usage: $0 --create-disposable uddns-broker-test-NAME"
name=$2
case "$name" in
  uddns-broker-test-?*) ;;
  *) die "VM name must start with uddns-broker-test- and have a suffix" ;;
esac
[[ "$name" =~ ^[a-z0-9-]+$ ]] || die "invalid VM name"
[[ "$name" != uddns-prealpha && "$name" != uddns-restore-test ]] ||
  die "protected VM name"
[[ $(id -u) -ne 0 ]] || die "run as a normal host user, not root"
command -v virsh >/dev/null || die "libvirt virsh missing"
command -v sudo >/dev/null || die "sudo missing"
if virsh -c qemu:///system dominfo "$name" >/dev/null 2>&1; then
  die "VM already exists; refusing reuse or overwrite"
fi
for file in "/var/lib/libvirt/images/$name.qcow2" "/var/lib/libvirt/images/$name-seed.iso"; do
  if sudo test -e "$file"; then
    die "existing VM artifact: $file"
  fi
done
repo=$(git rev-parse --show-toplevel) || die "run inside project repository"
[[ -f "$repo/tests/deployment/create-vm.sh" ]] || die "VM creator missing"
printf 'Creating new disposable VM %s using existing guarded creator\n' "$name"
VM="$name" bash "$repo/tests/deployment/create-vm.sh"
printf 'VM provisioning requested. Marker and broker units are NOT installed.\n'
