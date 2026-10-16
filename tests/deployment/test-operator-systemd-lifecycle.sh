#!/usr/bin/env bash
# Explicitly opt-in; dedicated disposable guest only. No production VM changes.
set -Eeuo pipefail
die() { printf 'FAIL: %s\n' "$*" >&2; exit 2; }
[[ $# -eq 1 && $1 == --run-disposable-lifecycle ]] || die "explicit opt-in required"
[[ $(id -u) -ne 0 ]] || die "run as an unprivileged operator"
ROOT=$(git rev-parse --show-toplevel) || die "run inside repository checkout"
bash "$ROOT/tests/deployment/check-operator-broker-preflight.sh" --preflight
for cmd in sudo systemctl systemd-analyze python3; do
  command -v "$cmd" >/dev/null || die "missing $cmd"
done
id universalddns >/dev/null || die "service account not provisioned"
getent group universalddns-operators >/dev/null || die "operator group not provisioned"
test -x /opt/universalddns/venv/bin/python || die "broker venv not provisioned"
socket_unit=/etc/systemd/system/universalddns-operator.socket
service_unit=/etc/systemd/system/universalddns-operator.service
cleanup() {
  result=$?
  trap - EXIT
  # Never report PASS when cleanup failed, and preserve units for diagnosis
  # if systemd could not stop the broker.
  if ! sudo systemctl stop universalddns-operator.socket universalddns-operator.service; then
    printf 'FAIL: broker stop failed; preserving test unit files for investigation\n' >&2
    exit 1
  fi
  if sudo systemctl is-active --quiet universalddns-operator.socket ||
     sudo systemctl is-active --quiet universalddns-operator.service; then
    printf 'FAIL: broker still active; preserving test unit files\n' >&2
    exit 1
  fi
  if ! sudo rm -f -- "$socket_unit" "$service_unit"; then
    printf 'FAIL: unable to remove broker test units\n' >&2
    exit 1
  fi
  if ! sudo systemctl daemon-reload; then
    printf 'FAIL: systemd reload after cleanup failed\n' >&2
    exit 1
  fi
  if [[ -e /run/universalddns/operator.sock || -L /run/universalddns/operator.sock ]]; then
    printf 'FAIL: broker socket path remains after shutdown\n' >&2
    exit 1
  fi
  exit "$result"
}
trap cleanup EXIT
sudo install -o root -g root -m 0644 "$ROOT/deploy/systemd/universalddns-operator.socket" "$socket_unit"
sudo install -o root -g root -m 0644 "$ROOT/deploy/systemd/universalddns-operator.service" "$service_unit"
sudo systemctl daemon-reload
sudo systemd-analyze verify "$socket_unit" "$service_unit"
sudo systemctl start universalddns-operator.socket
sudo systemctl is-active --quiet universalddns-operator.socket || die "socket not active"
test -S /run/universalddns/operator.sock || die "socket not created"
python3 - <<'PY'
import os, socket, stat
p = "/run/universalddns/operator.sock"
s = os.lstat(p)
assert stat.S_ISSOCK(s.st_mode)
assert stat.S_IMODE(s.st_mode) == 0o660
directory = os.lstat("/run/universalddns")
assert stat.S_ISDIR(directory.st_mode) and directory.st_uid == 0
assert not directory.st_mode & 0o022
assert directory.st_mode & stat.S_IXOTH
PY
# This smoke test does not yet verify peer authorization or successful ping.
sudo systemctl stop universalddns-operator.socket universalddns-operator.service
[[ ! -e /run/universalddns/operator.sock && ! -L /run/universalddns/operator.sock ]] || die "RemoveOnStop failed"
printf 'PASS: disposable socket creation, permissions, and cleanup\n'
