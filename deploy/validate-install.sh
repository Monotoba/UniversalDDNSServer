#!/bin/sh
# Read-only acceptance checks on an installed local UniversalDDNSServer.
set -eu
CONFIG="${1:-/etc/universalddns/config.json}"
SERVICE_USER="${SERVICE_USER:-universalddns}"
API_UNIT="${API_UNIT:-universalddns-api.service}"
WORKER_UNIT="${WORKER_UNIT:-universalddns-worker.service}"

test -f "$CONFIG" || { echo "Configuration is missing" >&2; exit 1; }
test -x /opt/universalddns/venv/bin/python || { echo "Installed Python environment missing" >&2; exit 1; }
test -x /opt/universalddns/venv/bin/uvicorn || { echo "Installed API server missing" >&2; exit 1; }

systemd-analyze verify "/etc/systemd/system/$API_UNIT" "/etc/systemd/system/$WORKER_UNIT"
systemctl is-active --quiet "$API_UNIT"
systemctl is-active --quiet "$WORKER_UNIT"

sudo -u "$SERVICE_USER" /opt/universalddns/venv/bin/python - "$CONFIG" <<'PY'
import sys
from universalddns.runtime import load_settings
from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
settings = load_settings(sys.argv[1])
with SQLiteIntentJournal(settings.database) as journal:
    journal.pending()
print("Configuration, credentials and SQLite access: OK")
PY

"$(dirname "$0")/smoke-check.sh"
echo "Local installation checks passed (DNS publishing and reboot not tested)."
