#!/bin/sh
# Local-only pre-alpha API smoke test. Does not send DNS updates.
set -eu
BASE_URL="${1:-http://127.0.0.1:8765}"
case "$BASE_URL" in
  http://127.0.0.1:*|http://localhost:*) ;;
  *) echo "Refusing non-loopback URL" >&2; exit 2 ;;
esac
python3 - "$BASE_URL" <<'PY'
import json
import sys
import urllib.request

url = sys.argv[1].rstrip("/")
with urllib.request.urlopen(url + "/health/live", timeout=5) as response:
    data = json.load(response)
    assert response.status == 200 and data == {"status": "live"}, data
print("Local API liveness: OK")

try:
    urllib.request.urlopen(url + "/api/v1/intents/nonexistent", timeout=5)
except urllib.error.HTTPError as exc:
    if exc.code != 401:
        raise AssertionError("Authentication guard returned " + str(exc.code))
    print("Unauthenticated intent access rejected: OK")
else:
    raise AssertionError("Unauthenticated intent access was not rejected")
PY
