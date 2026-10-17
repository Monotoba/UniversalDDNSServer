#!/usr/bin/env bash
# Read-only v0.5 dashboard smoke verification on an already-upgraded lab VM.
set -Eeuo pipefail
umask 077
command -v curl >/dev/null || { echo 'ERROR: curl required' >&2; exit 2; }
command -v python3 >/dev/null || { echo 'ERROR: python3 required' >&2; exit 2; }
base='http://127.0.0.1:8765'
record_id="${1:-}"
if [[ -z "$record_id" || ! "$record_id" =~ ^[a-zA-Z0-9._-]{1,128}$ ]]; then
  echo 'Usage: bash deploy/verify-v0.5-dashboard-readonly.sh ALLOWED_RECORD_ID' >&2
  exit 2
fi
if [[ ! -t 0 ]]; then
  echo 'ERROR: run interactively; token is read from terminal, never arguments' >&2
  exit 2
fi
read -r -s -p 'Existing scoped read-only bearer token: ' token
printf '\n'
if [[ -z "$token" ]]; then echo 'ERROR: empty token' >&2; exit 2; fi
tmp="$(mktemp -d)"
trap 'unset token; rm -rf "$tmp"' EXIT
# Supply bearer header over curl stdin rather than command-line arguments.
request() {
  local endpoint="$1" output="$2"
  printf 'header = "Authorization: Bearer %s"\n' "$token" |
    curl --config - --silent --show-error --max-time 12 --noproxy '*' \
      --output "$output" --write-out '%{http_code}' "$base$endpoint"
}
echo '=== Loopback dashboard assets (no credential) ==='
for endpoint in /dashboard /dashboard/app.js; do
  code="$(curl -sS --noproxy '*' --max-time 12 -o "$tmp/asset" -w '%{http_code}' "$base$endpoint")"
  [[ "$code" == 200 ]] || { echo "FAIL: $endpoint HTTP $code" >&2; exit 1; }
  echo "PASS: $endpoint HTTP 200"
done
echo '=== Unauthenticated API denied ==='
code="$(curl -sS --noproxy '*' --max-time 12 -o "$tmp/unauth" -w '%{http_code}' "$base/api/v1/records")"
[[ "$code" == 401 ]] || { echo "FAIL: unauthenticated records HTTP $code" >&2; exit 1; }
echo 'PASS: unauthenticated records HTTP 401'
echo '=== Authorized API read-only checks ==='
for pair in "records|/api/v1/records" "history|/api/v1/intents?limit=20" "detail|/api/v1/records/$record_id"; do
  name="${pair%%|*}"
  endpoint="${pair#*|}"
  code="$(request "$endpoint" "$tmp/$name")"
  [[ "$code" == 200 ]] || { echo "FAIL: $name HTTP $code" >&2; exit 1; }
  python3 - "$name" "$tmp/$name" "$record_id" <<'PY'
import json, sys
kind, filename, record_id = sys.argv[1:]
with open(filename, encoding="utf-8") as stream:
    data = json.load(stream)
if kind == "records":
    assert isinstance(data.get("records"), list)
    assert any(item.get("id") == record_id for item in data["records"])
elif kind == "history":
    assert isinstance(data.get("intents"), list) and len(data["intents"]) <= 20
    assert all({"intent_id", "record_id", "status", "created_at"} <= set(i)
               for i in data["intents"])
else:
    assert data["record"]["id"] == record_id
    assert data["authoritative"]["status"] in {
        "matches_template", "differs_from_template", "absent", "unavailable"
    }
print(f"PASS: {kind} schema and scope")
if kind == "detail":
    print("Observation status:", data["authoritative"]["status"])
PY
done
echo 'PASS: read-only dashboard smoke verification (no DNS writes attempted)'
echo 'Note: this does NOT verify DNS-write absence via audit, denial of other principals,'
echo 'a successful live authoritative lookup, rollback, or production security.'
