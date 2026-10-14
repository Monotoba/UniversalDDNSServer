#!/usr/bin/env bash
# Upgrade an existing disposable UniversalDDNS Ubuntu test VM.
set -Eeuo pipefail
REPO=/opt/universalddns/src
VENV=/opt/universalddns/venv
DB=/var/lib/universalddns/state.sqlite3
WORK_ROOT=/var/lib/universalddns
API=universalddns-api
WORKER=universalddns-worker
[[ "$(hostname -s)" == uddns-prealpha ]] || { echo "Refusing unexpected hostname" >&2; exit 2; }
systemd-detect-virt --vm >/dev/null || { echo "VM required" >&2; exit 2; }
[[ -f "$DB" && -d "$REPO/.git" && -x "$VENV/bin/python" ]] || { echo "Installed deployment missing" >&2; exit 2; }
sudo -n true || { echo "Passwordless sudo required for unattended recovery" >&2; exit 2; }
sudo systemctl is-active --quiet "$API"
sudo systemctl is-active --quiet "$WORKER"
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
  trap - ERR EXIT
  echo "Update failed (exit $status); restoring prior code and database"
  sudo systemctl stop "$WORKER" "$API" || true
  sudo git -C "$REPO" reset --hard "$BEFORE" || true
  sudo "$VENV/bin/python" -m pip install --no-deps --force-reinstall "$REPO" || true
  if [[ -f "$BACKUP/state.sqlite3" ]]; then
    sudo install -m 0600 -o universalddns -g universalddns "$BACKUP/state.sqlite3" "$DB"
  fi
  sudo systemctl start "$API" "$WORKER" || true
  echo "ROLLBACK_ATTEMPTED=YES; verify services manually. Backup retained at $BACKUP"
  exit "$status"
}
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
sudo "$VENV/bin/python" -m pip install --no-deps --upgrade --force-reinstall "$REPO"
sudo install -m 0644 "$REPO/deploy/universalddns-api.service" /etc/systemd/system/
sudo install -m 0644 "$REPO/deploy/universalddns-worker.service" /etc/systemd/system/
sudo systemctl daemon-reload
cp "$REPO/tests/deployment/vm-test.sh" "$HOME/vm-test.sh"
sudo systemctl start "$API" "$WORKER"
bash "$HOME/vm-test.sh" verify
trap - ERR
echo "FINAL_RESULT=PASS"
echo "Upgraded $BEFORE -> $AFTER. Backup retained: $BACKUP"
