#!/usr/bin/env bash
# Read-only preflight for the real, logged-in operator on an installed lab VM.
set -Eeuo pipefail
CONFIG="${1:-/etc/universalddns/config.json}"
PYTHON="${2:-/opt/universalddns/venv/bin/python}"
[[ "$(hostname -s)" == "uddns-prealpha" ]] || { echo "Refusing non-test VM hostname" >&2; exit 2; }
systemd-detect-virt --vm >/dev/null || { echo "Disposable VM required" >&2; exit 2; }
[[ $EUID -ne 0 && $UID -eq $EUID ]] || { echo "Run as the actual non-root operator login; do not use sudo" >&2; exit 2; }
[[ -x "$PYTHON" ]] || { echo "Missing installed Python interpreter" >&2; exit 2; }
"$PYTHON" - "$CONFIG" <<'PY'
import os
import sys
from universalddns.local_operator import local_operator_identity
from universalddns.runtime import load_admin_settings
from urllib.parse import quote

operator = local_operator_identity()
settings = load_admin_settings(sys.argv[1])
# Read-only SQLite connections avoid creating tables or writing schema migrations.
import sqlite3
uri = "file:" + quote(os.path.abspath(os.fspath(settings.database)), safe="/") + "?mode=ro"
with sqlite3.connect(uri, uri=True) as db:
    db.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
    for table in ("managed_records", "api_tokens", "credential_audit"):
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                            (table,)).fetchone()
        if not exists:
            raise RuntimeError("Required SQLite table missing: " + table)
print("PASS: authorized non-root operator, readable configuration and SQLite metadata")
PY
# Management CLIs may initialize/migrate stores; do not invoke them in a read-only preflight.
echo "PASS: operator preflight did not issue tokens, write SQLite or access DNS"
