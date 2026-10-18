#!/usr/bin/env bash
# Upgrade an existing disposable UniversalDDNS Ubuntu test VM.
set -Eeuo pipefail
# Installed application files must be readable by the service account.
umask 022
REPO=/opt/universalddns/src
VENV=/opt/universalddns/venv
DB=/var/lib/universalddns/state.sqlite3
WORK_ROOT=/var/lib/universalddns
API=universalddns-api
WORKER=universalddns-worker
MODE="${1:-update}"
if [[ $# -gt 1 || "$MODE" != update && "$MODE" != --verify ]]; then
  echo "Usage: bash update-vm.sh [--verify]" >&2
  exit 2
fi
[[ "$(hostname -s)" == uddns-prealpha ]] || { echo "Refusing unexpected hostname" >&2; exit 2; }
systemd-detect-virt --vm >/dev/null || { echo "VM required" >&2; exit 2; }
sudo -n true || { echo "Passwordless sudo required for unattended recovery" >&2; exit 2; }
sudo test -f "$DB" || { echo "SQLite file missing or inaccessible to root: $DB" >&2; exit 2; }
sudo git -C "$REPO" rev-parse --is-inside-work-tree | grep -Fxq true || { echo "Git checkout invalid: $REPO" >&2; exit 2; }
sudo test -x "$VENV/bin/python" || { echo "Virtual environment missing: $VENV" >&2; exit 2; }
sudo systemctl is-active --quiet "$API"
sudo systemctl is-active --quiet "$WORKER"
# systemd active does not guarantee that the TCP listener is ready.
# Bound the wait and print service diagnostics if startup never completes.
wait_for_api() {
  local i
  for ((i=0; i<30; i++)); do
    if sudo systemctl is-active --quiet "$API" &&
       sudo systemctl is-active --quiet "$WORKER" &&
       "$VENV/bin/python" -c 'import socket; s=socket.create_connection(("127.0.0.1",8765),timeout=1); s.close()' 2>/dev/null; then
      echo "API ready on 127.0.0.1:8765"
      return 0
    fi
    sleep 1
  done
  echo "API not ready after 30 seconds" >&2
  sudo systemctl status --no-pager "$API" "$WORKER" >&2 || true
  return 1
}
# Verify actual runtime imports as the unprivileged service account.
# pip show/check alone cannot detect unreadable installed Python files.
verify_service_imports() {
  sudo -u universalddns "$VENV/bin/python" - <<'PYIMPORT'
import universalddns.runtime
from universalddns.runtime import api_app
print("SERVICE_ACCOUNT_IMPORT=PASS")
PYIMPORT
}
if [[ "$MODE" == "--verify" ]]; then
  echo "Checking installed Python distribution and runtime services (no Git update)"
  sudo "$VENV/bin/python" -m pip show universalddnsserver || exit 1
  verify_service_imports
  bash "$REPO/tests/deployment/vm-test.sh" verify
  echo "FINAL_RESULT=PASS"
  exit 0
fi
[[ -z "$(sudo git -C "$REPO" status --porcelain)" ]] || { echo "Source checkout is dirty; refusing" >&2; exit 2; }
BEFORE=$(sudo git -C "$REPO" rev-parse HEAD)
sudo git -C "$REPO" fetch --prune origin main
AFTER=$(sudo git -C "$REPO" rev-parse origin/main)
sudo git -C "$REPO" merge-base --is-ancestor "$BEFORE" "$AFTER" || { echo "Not a fast-forward" >&2; exit 2; }
if [[ "$BEFORE" == "$AFTER" ]]; then echo "Already current: $BEFORE"; exit 0; fi
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="$WORK_ROOT/upgrade-backup-$STAMP"
sudo install -d -o universalddns -g universalddns -m 0700 "$BACKUP"
LOG="$HOME/uddns-update-$STAMP.log"
exec > >(tee "$LOG") 2>&1
echo "BEFORE=$BEFORE"
echo "AFTER=$AFTER"
echo "BACKUP=$BACKUP"
rollback() {
  local status=$?
  local recovery_failed=0
  trap - ERR EXIT
  # Continue recovery after individual failures; preserve the original status.
  set +e

  echo "Update failed (exit $status); restoring prior code and database"

  sudo systemctl stop "$WORKER" "$API" || recovery_failed=1

  if ! sudo git -C "$REPO" reset --hard "$BEFORE"; then
    echo "WARNING: Git restoration failed" >&2
    recovery_failed=1
  fi

  if ! sudo sh -c 'umask 022; exec "$@"' sh \
      "$VENV/bin/python" -m pip install --no-deps \
      --force-reinstall "$REPO"; then
    echo "WARNING: Package restoration failed" >&2
    recovery_failed=1
  fi

  if ! verify_service_imports; then
    echo "WARNING: Restored runtime import failed" >&2
    recovery_failed=1
  fi

  if [[ -f "$BACKUP/state.sqlite3" ]]; then
    if ! sudo install -m 0600 -o universalddns -g universalddns \
        "$BACKUP/state.sqlite3" "$DB"; then
      echo "WARNING: Database restoration failed" >&2
      recovery_failed=1
    fi
  else
    echo "WARNING: Database backup missing" >&2
    recovery_failed=1
  fi

  if [[ -f "$BACKUP/universalddns-api.service" &&
        -f "$BACKUP/universalddns-worker.service" ]]; then
    if ! sudo install -m 0644 "$BACKUP/universalddns-api.service" \
        /etc/systemd/system/universalddns-api.service; then
      echo "WARNING: API unit restoration failed" >&2
      recovery_failed=1
    fi

    if ! sudo install -m 0644 "$BACKUP/universalddns-worker.service" \
        /etc/systemd/system/universalddns-worker.service; then
      echo "WARNING: Worker unit restoration failed" >&2
      recovery_failed=1
    fi

    if ! sudo systemctl daemon-reload; then
      echo "WARNING: systemd reload failed" >&2
      recovery_failed=1
    fi
  else
    echo "WARNING: Original service-unit backup incomplete" >&2
    recovery_failed=1
  fi

  if ! sudo systemctl start "$API" "$WORKER"; then
    echo "WARNING: Service restart failed" >&2
    recovery_failed=1
  fi

  if wait_for_api && verify_service_imports; then
    echo "ROLLBACK_SERVICES=READY"
  else
    echo "ROLLBACK_SERVICES=UNVERIFIED" >&2
    recovery_failed=1
  fi

  if (( recovery_failed == 0 )); then
    echo "ROLLBACK_OPERATIONS=PASS"
  else
    echo "ROLLBACK_OPERATIONS=FAILED" >&2
  fi

  echo "ROLLBACK_ATTEMPTED=YES; original upgrade failure retained. Backup: $BACKUP"
  exit "$status"
}

# Complete non-destructive preflight backups before arming rollback.
# A failed unit backup must not trigger a package reinstall.
echo "Preserving currently installed service units"
sudo install -m 0600 /etc/systemd/system/universalddns-api.service \
  "$BACKUP/universalddns-api.service"
sudo install -m 0600 /etc/systemd/system/universalddns-worker.service \
  "$BACKUP/universalddns-worker.service"

# Every operation below may require application-level recovery.
trap rollback ERR
sudo systemctl stop "$WORKER" "$API"
# Offline database snapshot: no app writer is running. Preserve WAL contents
# by using sqlite3's online backup API rather than copying one file.
sudo -u universalddns "$VENV/bin/python" - "$DB" "$BACKUP/state.sqlite3" <<'PY'
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as src, sqlite3.connect(sys.argv[2]) as dst:
    src.backup(dst)
    assert dst.execute("PRAGMA integrity_check").fetchone() == ("ok",)
PY
sudo chmod 0600 "$BACKUP/state.sqlite3"
sudo git -C "$REPO" merge --ff-only "$AFTER"
sudo sh -c 'umask 022; exec "$@"' sh "$VENV/bin/python" -m pip install --no-deps --upgrade --force-reinstall "$REPO"
verify_service_imports
sudo install -m 0644 "$REPO/deploy/universalddns-api.service" /etc/systemd/system/
sudo install -m 0644 "$REPO/deploy/universalddns-worker.service" /etc/systemd/system/
sudo systemctl daemon-reload
cp "$REPO/tests/deployment/vm-test.sh" "$HOME/vm-test.sh"
sudo systemctl start "$API" "$WORKER"
wait_for_api
bash "$HOME/vm-test.sh" verify
trap - ERR
echo "FINAL_RESULT=PASS"
echo "Upgraded $BEFORE -> $AFTER. Backup retained: $BACKUP"
