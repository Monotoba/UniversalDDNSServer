#!/bin/sh
# Local-only pre-alpha API smoke test. Does not send DNS updates.
set -eu
BASE_URL="${1:-http://127.0.0.1:8765}"
python3 - "$BASE_URL" <<'PY'
import json
import sys
import urllib.request
import urllib.error
import urllib.parse

url = sys.argv[1].rstrip("/")
parsed = urllib.parse.urlsplit(url)
if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost") or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
    raise SystemExit("Refusing non-loopback API URL")
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
