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
  echo "Usage: sudo bash update-vm.sh [--verify]" >&2
  exit 2
fi
# Require privileged execution for the upgrade lock.
if (( EUID != 0 )); then
  echo "Run updater with sudo" >&2
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
LOCK_DIR=/run/lock/universalddns
if [[ -L "$LOCK_DIR" ]]; then
  echo "Refusing symbolic-link upgrade lock directory" >&2
  exit 2
fi
if [[ -e "$LOCK_DIR" ]]; then
  [[ -d "$LOCK_DIR" ]] || exit 2
  test "$(stat -c '%u:%g:%a' "$LOCK_DIR")" = "0:0:700" || exit 2
else
  install -d -o root -g root -m 0700 "$LOCK_DIR"
fi
test "$(stat -c '%u:%g:%a' "$LOCK_DIR")" = "0:0:700" || exit 2
LOCK_FILE="$LOCK_DIR/upgrade.lock"
if [[ -L "$LOCK_FILE" ]]; then
  echo "Refusing symbolic-link upgrade lock" >&2
  exit 2
fi
if [[ -e "$LOCK_FILE" ]]; then
  [[ -f "$LOCK_FILE" ]] || exit 2
  test "$(stat -c "%u:%g:%a" "$LOCK_FILE")" = "0:0:600" || exit 2
fi
exec 9>>"$LOCK_FILE"
chmod 0600 "$LOCK_FILE"
if ! flock -n 9; then
  echo "Upgrade already running" >&2
  exit 2
fi
echo "UPGRADE_LOCK=ACQUIRED"

[[ -z "$(sudo git -C "$REPO" status --porcelain)" ]] || { echo "Source checkout is dirty; refusing" >&2; exit 2; }
BEFORE=$(sudo git -C "$REPO" rev-parse HEAD)
sudo git -C "$REPO" fetch --prune origin main
AFTER=$(sudo git -C "$REPO" rev-parse origin/main)
sudo git -C "$REPO" merge-base --is-ancestor "$BEFORE" "$AFTER" || { echo "Not a fast-forward" >&2; exit 2; }
if [[ "$BEFORE" == "$AFTER" ]]; then echo "Already current: $BEFORE"; exit 0; fi
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="/var/backups/universalddns/upgrade-backup-$STAMP"
DB_BACKUP="$WORK_ROOT/upgrade-backup-$STAMP"

# Privileged artifacts must be outside the service-writable tree.
BACKUP_ROOT=/var/backups/universalddns

if [[ -L "$BACKUP_ROOT" ]]; then
  echo "Refusing symbolic-link recovery directory" >&2
  exit 2
fi

if [[ -e "$BACKUP_ROOT" ]]; then
  [[ -d "$BACKUP_ROOT" ]] || exit 2
  test "$(stat -c '%u:%g:%a' "$BACKUP_ROOT")" = "0:0:700" || exit 2
else
  install -d -o root -g root -m 0700 "$BACKUP_ROOT"
fi

test "$(stat -c '%u:%g:%a' "$BACKUP_ROOT")" = "0:0:700" || exit 2

# Never reuse an existing recovery directory. mkdir is atomic, so
# simultaneous attempts cannot claim the same privileged backup path.
if ! sudo mkdir -m 0700 "$BACKUP"; then
  echo "Recovery backup already exists or cannot be created: $BACKUP" >&2
  exit 2
fi

# Keep the database snapshot under the service account's ownership.
# Refuse an existing DB backup rather than mixing recovery generations.
if ! sudo -u universalddns mkdir -m 0700 "$DB_BACKUP"; then
  echo "Database backup already exists or cannot be created: $DB_BACKUP" >&2
  exit 2
fi
LOG="$BACKUP/upgrade.log"
exec > >(tee "$LOG") 2>&1
echo "BEFORE=$BEFORE"
echo "AFTER=$AFTER"
echo "BACKUP=$BACKUP"
echo "DB_BACKUP=$DB_BACKUP"
rollback() {
  local status=$?
  local recovery_failed=0
  local db_recovery_failed=0
  trap - ERR EXIT
  # Continue recovery after individual failures; preserve the original status.
  set +e

  echo "Update failed (exit $status); restoring prior code and database"

  sudo systemctl stop "$WORKER" "$API" || recovery_failed=1

  if ! sudo git -C "$REPO" reset --hard "$BEFORE"; then
    echo "WARNING: Git restoration failed" >&2
    recovery_failed=1
  fi

  local verified_sha=""
  if [[ -f "$RECOVERY_WHEEL" ]]; then
    verified_sha=$(sudo sha256sum "$RECOVERY_WHEEL") || verified_sha=""
    verified_sha="${verified_sha%% *}"
  fi
  if [[ -z "$verified_sha" || "$verified_sha" != "$RECOVERY_SHA" ]] ||
     ! sudo sh -c 'umask 022; exec "$@"' sh \
         "$VENV/bin/python" -m pip install \
         --no-index --no-deps --force-reinstall "$RECOVERY_WHEEL"; then
    echo "WARNING: Package restoration failed" >&2
    recovery_failed=1
  fi

  if ! verify_service_imports; then
    echo "WARNING: Restored runtime import failed" >&2
    recovery_failed=1
  fi

  # Never restore an incomplete or unverified database snapshot.
  if [[ "${DB_SNAPSHOT_READY:-0}" == 1 ]]; then
    local db_sha=""
    if [[ -f "$BACKUP/state.sqlite3" ]]; then
      db_sha=$(sudo sha256sum "$BACKUP/state.sqlite3") || db_sha=""
      db_sha="${db_sha%% *}"
    fi

    if [[ -n "$db_sha" && "$db_sha" == "${DB_RECOVERY_SHA:-}" ]]; then
      if ! sudo "$VENV/bin/python" \
          - "$BACKUP/state.sqlite3" "$DB" <<'PYDBRESTORE'
import sqlite3
import sys

source, target = sys.argv[1:]

import os
import pwd
import grp
import stat

info = os.stat(target)
expected_uid = pwd.getpwnam("universalddns").pw_uid
expected_gid = grp.getgrnam("universalddns").gr_gid

if info.st_uid != expected_uid or info.st_gid != expected_gid:
    raise RuntimeError("Restored database ownership mismatch")

if stat.S_IMODE(info.st_mode) != 0o600:
    raise RuntimeError("Restored database permissions mismatch")

with sqlite3.connect(source) as src:
    with sqlite3.connect(
        "file:" + target + "?mode=rw", uri=True
    ) as dst:
        src.backup(dst)
        result = dst.execute("PRAGMA integrity_check").fetchone()
        if result != ("ok",):
            raise RuntimeError(f"Restored database integrity failure: {result}")

# Verify metadata again after restoration.
info = os.stat(target)
expected_uid = pwd.getpwnam("universalddns").pw_uid
expected_gid = grp.getgrnam("universalddns").gr_gid

if info.st_uid != expected_uid or info.st_gid != expected_gid:
    raise RuntimeError("Restored database ownership mismatch")

if stat.S_IMODE(info.st_mode) != 0o600:
    raise RuntimeError("Restored database permissions mismatch")

print("ROLLBACK_DATABASE=RESTORED")
PYDBRESTORE
      then
        echo "WARNING: Database restoration failed" >&2
        db_recovery_failed=1
        recovery_failed=1
      fi
    else
      echo "WARNING: Protected database snapshot verification failed" >&2
      db_recovery_failed=1
      recovery_failed=1
    fi
  else
    echo "ROLLBACK_DATABASE=SKIPPED_NO_VERIFIED_SNAPSHOT"
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

  if (( db_recovery_failed != 0 )); then
    echo "ROLLBACK_SERVICES=BLOCKED_DATABASE_RECOVERY" >&2
    recovery_failed=1
  elif (( recovery_failed != 0 )); then
    echo "ROLLBACK_SERVICES=BLOCKED_INCOMPLETE_RECOVERY" >&2
  else
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

  fi

  if (( recovery_failed == 0 )); then
    echo "ROLLBACK_OPERATIONS=PASS"
  else
    echo "ROLLBACK_OPERATIONS=FAILED" >&2
  fi

  echo "ROLLBACK_ATTEMPTED=YES; original upgrade failure retained. Backup: $BACKUP"
  exit "$status"
}

# Prepare the offline recovery artifact before stopping services.
# Refuse an upgrade if the installed code cannot be reconstructed.
echo "Preparing offline recovery wheel"

RECOVERY_DIR="$BACKUP/recovery-wheel"
sudo install -d -m 0700 "$RECOVERY_DIR"

sudo "$VENV/bin/python" - "$REPO" <<'PYVERSION'
import importlib.metadata
import pathlib
import sys
import tomllib

source = pathlib.Path(sys.argv[1])
project = tomllib.loads((source / "pyproject.toml").read_text())

expected = project["project"]["version"]
installed = importlib.metadata.version("universalddnsserver")

assert expected == installed, (expected, installed)
print("RECOVERY_VERSION=PASS")
PYVERSION

# Use system build tooling, not the application virtual environment.
# This prevents packaging prerequisites from altering runtime dependencies.
sudo /usr/bin/python3 -c 'import setuptools.build_meta, wheel'

sudo sh -c 'umask 022; exec "$@"' sh \
  /usr/bin/python3 -m pip wheel \
  --no-index --no-deps --no-build-isolation \
  --wheel-dir "$RECOVERY_DIR" "$REPO"

RECOVERY_WHEELS=("$RECOVERY_DIR"/universalddnsserver-*.whl)
if (( ${#RECOVERY_WHEELS[@]} != 1 )) ||
   [[ ! -f "${RECOVERY_WHEELS[0]}" ]]; then
  echo "Recovery wheel missing or ambiguous; refusing upgrade" >&2
  exit 2
fi

RECOVERY_WHEEL="${RECOVERY_WHEELS[0]}"

# Verify that wheel contents match the actual installed package files.
sudo "$VENV/bin/python" - "$RECOVERY_WHEEL" <<'PYCOMPARE'
import importlib.metadata
import pathlib
import sys
import zipfile
from email.parser import Parser

wheel = pathlib.Path(sys.argv[1])
dist = importlib.metadata.distribution("universalddnsserver")

with zipfile.ZipFile(wheel) as archive:
    assert archive.testzip() is None

    names = archive.namelist()
    package_files = [
        name for name in names
        if name.startswith("universalddns/")
        and not name.endswith("/")
    ]
    assert package_files

    installed_files = {
        str(item).replace("\\", "/")
        for item in dist.files or ()
        if str(item).replace("\\", "/").startswith("universalddns/")
        and str(item).endswith(".py")
    }
    wheel_files = {
        name for name in package_files if name.endswith(".py")
    }
    assert installed_files == wheel_files, (
        sorted(installed_files - wheel_files),
        sorted(wheel_files - installed_files),
    )

    for name in package_files:
        installed = pathlib.Path(dist.locate_file(name))
        assert installed.is_file(), name
        assert installed.read_bytes() == archive.read(name), name

    metadata_names = [
        name for name in names
        if name.endswith(".dist-info/METADATA")
    ]
    assert len(metadata_names) == 1

    metadata = Parser().parsestr(
        archive.read(metadata_names[0]).decode()
    )
    assert metadata["Name"].lower() == "universalddnsserver"
    assert metadata["Version"] == dist.version

print("RECOVERY_CONTENTS=PASS")
PYCOMPARE

RECOVERY_SHA=$(sudo sha256sum "$RECOVERY_WHEEL" | cut -d' ' -f1)
echo "RECOVERY_WHEEL=$RECOVERY_WHEEL"
echo "RECOVERY_SHA256=$RECOVERY_SHA"
echo "RECOVERY_PREFLIGHT=PASS"

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
sudo -u universalddns "$VENV/bin/python" - "$DB" "$DB_BACKUP/state.sqlite3" <<'PY'
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as src, sqlite3.connect(sys.argv[2]) as dst:
    src.backup(dst)
    assert dst.execute("PRAGMA integrity_check").fetchone() == ("ok",)
PY
sudo chmod 0600 "$DB_BACKUP/state.sqlite3"

# Preserve the completed SQLite snapshot in root-controlled storage.
sudo install -o root -g root -m 0600   "$DB_BACKUP/state.sqlite3" "$BACKUP/state.sqlite3"

# Independently validate the protected recovery copy.
sudo "$VENV/bin/python" - "$BACKUP/state.sqlite3" <<'PYDBVERIFY'
import sqlite3
import sys

uri = "file:" + sys.argv[1] + "?mode=ro"
with sqlite3.connect(uri, uri=True) as db:
    result = db.execute("PRAGMA integrity_check").fetchone()
    if result != ("ok",):
        raise RuntimeError(f"Recovery database integrity failure: {result}")
print("PROTECTED_DB_INTEGRITY=PASS")
PYDBVERIFY

DB_RECOVERY_SHA=$(sudo sha256sum "$BACKUP/state.sqlite3") || {
  echo "Protected SQLite snapshot checksum failed" >&2
  false
}
DB_RECOVERY_SHA="${DB_RECOVERY_SHA%% *}"

if [[ ! "$DB_RECOVERY_SHA" =~ ^[[:xdigit:]]{64}$ ]]; then
  echo "Invalid protected SQLite snapshot checksum" >&2
  false
fi

DB_SNAPSHOT_READY=1
echo "DB_RECOVERY_SHA256=$DB_RECOVERY_SHA"
sudo git -C "$REPO" merge --ff-only "$AFTER"
# Explicitly pass optional pip configuration across sudo's environment boundary.
# Keep normal pip behavior when no offline wheelhouse is configured.
PIP_ENV=()
[[ -z "${PIP_NO_INDEX:-}" ]] || PIP_ENV+=("PIP_NO_INDEX=$PIP_NO_INDEX")
[[ -z "${PIP_FIND_LINKS:-}" ]] || PIP_ENV+=("PIP_FIND_LINKS=$PIP_FIND_LINKS")

sudo sh -c 'umask 022; exec "$@"' sh \
  /usr/bin/env "${PIP_ENV[@]}" \
  "$VENV/bin/python" -m pip install \
  --no-deps --upgrade --force-reinstall "$REPO"
verify_service_imports
sudo install -m 0644 "$REPO/deploy/universalddns-api.service" /etc/systemd/system/
sudo install -m 0644 "$REPO/deploy/universalddns-worker.service" /etc/systemd/system/
sudo systemctl daemon-reload

sudo systemctl start "$API" "$WORKER"
wait_for_api
bash "$REPO/tests/deployment/vm-test.sh" verify
trap - ERR
echo "FINAL_RESULT=PASS"
echo "Upgraded $BEFORE -> $AFTER. Backup retained: $BACKUP"
