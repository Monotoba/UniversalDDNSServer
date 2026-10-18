#!/usr/bin/env bash
# Read-only admission gate for an explicitly disposable, isolated broker test VM.
set -Eeuo pipefail
fail() { printf 'REFUSED: %s\n' "$*" >&2; exit 2; }
[[ $# -eq 1 && $1 == --preflight ]] || fail "pass --preflight (no installation is performed)"
[[ $(id -u) -ne 0 ]] || fail "invoke as an unprivileged VM operator, not root"
[[ -f /etc/os-release ]] || fail "missing OS identity"
# The marker must be deliberately provisioned inside the disposable guest.
MARKER=/etc/universalddns-broker-disposable-test
[[ -f "$MARKER" && ! -L "$MARKER" ]] || fail "disposable-guest marker missing"
[[ $(cat "$MARKER") == 'UNIVERSALDDNS_DISPOSABLE_BROKER_TEST_V1' ]] ||
  fail "disposable-guest marker invalid"
[[ $(stat -c '%u:%a' "$MARKER") == '0:644' ]] ||
  fail "marker must be root-owned and mode 0644"
command -v systemd-detect-virt >/dev/null || fail "systemd-detect-virt missing"
[[ $(systemd-detect-virt --vm) != none ]] || fail "not in a virtual machine"
[[ -d /run/systemd/system ]] || fail "systemd is not the system manager"
host=$(hostname -s)
case "$host" in
  uddns-prealpha|uddns-restore-test) fail "protected VM: $host" ;;
  uddns-broker-test-*) ;;
  *) fail "hostname must begin uddns-broker-test-" ;;
esac
[[ ! -e /run/universalddns/operator.sock && ! -L /run/universalddns/operator.sock ]] ||
  fail "operator socket already exists"
for unit in universalddns-operator.socket universalddns-operator.service; do
  # A vendor unit, mask, symlink or drop-in can shadow/change test units.
  for base in /etc/systemd/system /run/systemd/system /usr/lib/systemd/system /lib/systemd/system; do
    [[ ! -e "$base/$unit" && ! -L "$base/$unit" ]] ||
      fail "broker unit already installed: $base/$unit"
    [[ ! -e "$base/$unit.d" && ! -L "$base/$unit.d" ]] ||
      fail "broker unit drop-in already installed: $base/$unit.d"
  done
done
command -v systemctl >/dev/null || fail "systemctl missing"
if systemctl is-active --quiet universalddns-operator.socket ||
   systemctl is-active --quiet universalddns-operator.service; then
  fail "broker is already active"
fi
printf 'PASS: disposable guest admission only; no units installed or started\n'
