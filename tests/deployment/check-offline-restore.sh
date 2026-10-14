#!/usr/bin/env bash
# Disposable-VM-only offline database cutover and restoration check.
set -Eeuo pipefail
[[ "${1:-}" == "--i-understand-this-stops-services" ]] || { echo "Explicit acknowledgement required" >&2; exit 2; }
systemd-detect-virt --vm >/dev/null || { echo "Refusing non-VM host" >&2; exit 2; }
[[ "$(hostname -s)" == "uddns-prealpha" ]] || { echo "Unexpected hostname; refusing" >&2; exit 2; }
DB=/var/lib/universalddns/state.sqlite3
PY=/opt/universalddns/venv/bin/python
[[ -f "$DB" ]] || { echo "Missing SQLite database" >&2; exit 2; }
[[ -x "$PY" ]] || exit 2
systemctl is-active --quiet universalddns-api
systemctl is-active --quiet universalddns-worker
WORK=$(mktemp -d /var/lib/universalddns/.offline-restore.XXXXXXXX)
chmod 0700 "$WORK"
RESTORED=0
cleanup() {
  local result=$?
  trap - EXIT
  if [[ $RESTORED -eq 1 ]]; then
    cp -f "$WORK/original.db" "$DB"
    chown universalddns:universalddns "$DB"
    chmod 0600 "$DB"
  fi
  systemctl start universalddns-api universalddns-worker || result=1
  rm -rf -- "$WORK"
  exit "$result"
}
trap cleanup EXIT
systemctl stop universalddns-api universalddns-worker
# Services are stopped, so no more concurrent database writers.
cp -- "$DB" "$WORK/original.db"
chmod 0600 "$WORK/original.db"
# Validate the offline backup without modifying the original.
"$PY" - "$WORK/original.db" <<'PY'
import sqlite3, sys
with sqlite3.connect(sys.argv[1]) as db:
    assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert db.execute("SELECT count(*) FROM update_intents").fetchone()[0] > 0
PY
# Restore the offline snapshot into a new database file, then switch atomically.
cp -- "$WORK/original.db" "$WORK/restored.db"
chown universalddns:universalddns "$WORK/restored.db"
chmod 0600 "$WORK/restored.db"
mv -f -- "$WORK/restored.db" "$DB"
RESTORED=1
"$PY" - "$WORK/original.db" "$DB" <<'PY'
import sqlite3,sys
def dump(path):
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        return tuple(db.iterdump())
assert dump(sys.argv[1]) == dump(sys.argv[2]), "Offline restored data mismatch"
print("PASS: offline restored database matches original snapshot")
PY
test "$(stat -c '%a' "$DB")" = 600
test "$(stat -c '%U:%G' "$DB")" = universalddns:universalddns
RESTORED=0
systemctl start universalddns-api universalddns-worker
systemctl is-active --quiet universalddns-api
systemctl is-active --quiet universalddns-worker
echo "PASS: restored SQLite ownership, permissions, contents and systemd startup"
