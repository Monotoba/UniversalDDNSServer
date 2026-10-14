#!/usr/bin/env bash
set -Eeuo pipefail
MODE="${1:-verify}"
ROOT="$HOME/uddns-results"
mkdir -p "$ROOT"; chmod 700 "$ROOT"
LOG="$ROOT/$(date -u +%Y%m%dT%H%M%SZ)-$MODE.log"
exec > >(tee "$LOG") 2>&1
on_exit() { local code=$?; echo "FINAL_RESULT=$([[ $code -eq 0 ]] && echo PASS || echo FAIL)"; echo "LOG=$LOG"; }
trap on_exit EXIT
systemd-detect-virt --vm >/dev/null || { echo "Run only inside disposable VM" >&2; exit 2; }
case "$MODE" in
install)
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y git python3-venv python3-pip bind9 bind9-utils dnsutils curl
  id universalddns >/dev/null 2>&1 || sudo useradd --system --home-dir /var/lib/universalddns --shell /usr/sbin/nologin universalddns
  sudo install -d -m 0750 -o universalddns -g universalddns /var/lib/universalddns
  sudo install -d -m 0700 -o universalddns -g universalddns /etc/universalddns
  sudo install -d -m 0755 /opt/universalddns
  [[ ! -e /opt/universalddns/src ]] || { echo "Installation directory already present: refusing overwrite" >&2; exit 1; }
  sudo git clone https://github.com/Monotoba/UniversalDDNSServer.git /opt/universalddns/src
  sudo python3 -m venv /opt/universalddns/venv
  sudo /opt/universalddns/venv/bin/pip install '/opt/universalddns/src[api,dev]' requests
  KEY=$(python3 -c 'import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())')
  sudo bash -c 'umask 077; cat > /etc/bind/uddns-lab.key' <<KEYFILE
key "uddns-lab." { algorithm hmac-sha256; secret "$KEY"; };
KEYFILE
  sudo chown root:bind /etc/bind/uddns-lab.key
  sudo chmod 0640 /etc/bind/uddns-lab.key
  sudo tee /var/lib/bind/uddns-lab.zone >/dev/null <<'ZONE'
$TTL 60
@ IN SOA ns.lab.invalid. hostmaster.lab.invalid. ( 1 3600 600 604800 60 )
@ IN NS ns.lab.invalid.
ns IN A 127.0.0.1
ZONE
  sudo chown bind:bind /var/lib/bind/uddns-lab.zone
  sudo tee /etc/bind/named.conf.options >/dev/null <<'OPTIONS'
options {
  directory "/var/cache/bind";
  recursion no;
  listen-on port 53 { 127.0.0.1; };
  listen-on-v6 { none; };
  allow-query { 127.0.0.1; };
  dnssec-validation no;
};
OPTIONS
  sudo tee /etc/bind/named.conf.local >/dev/null <<'BIND'
include "/etc/bind/uddns-lab.key";
zone "lab.invalid" {
  type primary;
  file "/var/lib/bind/uddns-lab.zone";
  update-policy { grant uddns-lab. zonesub A AAAA; };
};
BIND
  sudo named-checkconf -z
  sudo systemctl restart named
  sudo python3 - "$KEY" <<'PY'
import json,sys,os
p='/etc/universalddns/tsig.json'
with open(p,'w',encoding='utf8') as f: json.dump({'key_secret':sys.argv[1]},f)
os.chmod(p,0o600)
PY
  sudo chown universalddns:universalddns /etc/universalddns/tsig.json
  unset KEY
  sudo tee /etc/universalddns/config.json >/dev/null <<'CONFIG'
{
  "database": "/var/lib/universalddns/state.sqlite3",
  "credentials": "/etc/universalddns/tsig.json",
  "dns": {"zone":"lab.invalid","server":"127.0.0.1","port":53,"key_name":"uddns-lab."},
  "interval": 0.2,
  "records": {"home":{"name":"home.lab.invalid","type":"A","ttl":60,"address":"192.0.2.10"}}
}
CONFIG
  sudo chown universalddns:universalddns /etc/universalddns/config.json
  sudo chmod 0600 /etc/universalddns/config.json
  sudo install -m 0644 /opt/universalddns/src/deploy/universalddns-api.service /etc/systemd/system/
  sudo install -m 0644 /opt/universalddns/src/deploy/universalddns-worker.service /etc/systemd/system/
  sudo systemctl daemon-reload
  umask 077
  sudo -u universalddns /opt/universalddns/venv/bin/python -m universalddns.admin \
    --config /etc/universalddns/config.json issue --principal vm-test \
    --record home --scope records:write --scope intents:read > "$HOME/.uddns-vm-token"
  sudo systemctl enable --now universalddns-api universalddns-worker
  bash "$0" verify
  bash "$0" update
  ;;
verify)
  grep -E '^(PRETTY_NAME|VERSION_ID)=' /etc/os-release
  python3 --version
  cat /proc/sys/kernel/random/boot_id
  sudo systemd-analyze verify /etc/systemd/system/universalddns-{api,worker}.service
  sudo systemctl is-active universalddns-api universalddns-worker named
  sudo /opt/universalddns/src/deploy/validate-install.sh
  ss -lnt | grep -Eq '127\.0\.0\.1:8765\b' || { echo "Expected loopback listener missing" >&2; exit 1; }
  ;;
update)
  test -s "$HOME/.uddns-vm-token"
  TOKEN_FILE="$HOME/.uddns-vm-token" /opt/universalddns/venv/bin/python - <<'PY'
import json, os, time, uuid, urllib.request
import dns.resolver
base='http://127.0.0.1:8765'
with open(os.environ['TOKEN_FILE'],encoding='utf8') as f: token=f.read().strip()
headers={'Authorization':'Bearer '+token, 'Content-Type':'application/json'}
body=json.dumps({'address':'192.0.2.42','request_id':'vm-'+uuid.uuid4().hex}).encode()
request=urllib.request.Request(base+'/api/v1/records/home/address',data=body,headers=headers,method='PUT')
with urllib.request.urlopen(request,timeout=8) as response:
    assert response.status==202
    identifier=json.load(response)['intent_id']
for _ in range(60):
    request=urllib.request.Request(base+'/api/v1/intents/'+identifier,headers=headers)
    with urllib.request.urlopen(request,timeout=5) as response:
        status=json.load(response)['status']
    if status=='applied': break
    if status=='failed': raise RuntimeError('Worker failed')
    time.sleep(.5)
else: raise RuntimeError('Worker did not apply within 30s')
resolver=dns.resolver.Resolver(configure=False)
resolver.nameservers=['127.0.0.1']
resolver.port=53
seen={answer.address for answer in resolver.resolve('home.lab.invalid','A',search=False)}
assert seen=={'192.0.2.42'},seen
print('PASS: scoped API, worker and authoritative BIND A update')
PY
  ;;
backup)
  sudo -u universalddns /opt/universalddns/venv/bin/python - <<'PY'
import sqlite3,tempfile
from pathlib import Path
source=Path('/var/lib/universalddns/state.sqlite3')
with tempfile.TemporaryDirectory(dir='/var/lib/universalddns') as td:
    backup=Path(td)/'backup.sqlite3'
    with sqlite3.connect(source) as src,sqlite3.connect(backup) as dst: src.backup(dst)
    with sqlite3.connect(backup) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
print('PASS: non-destructive SQLite backup integrity')
PY
  ;;
report)
  sudo systemctl is-enabled universalddns-api universalddns-worker > "$ROOT/enabled-services.txt"
  sudo systemctl status --no-pager universalddns-api universalddns-worker named | sed -E 's/(Bearer )[[:graph:]]+/\1[REDACTED]/g' > "$ROOT/service-status.txt" || true
  sudo journalctl -u universalddns-api -u universalddns-worker -u named --since '1 day ago' --no-pager -n 300 | sed -E 's/(Bearer )[[:graph:]]+/\1[REDACTED]/g' > "$ROOT/journal-sanitized.txt" || true
  dpkg-query -W bind9 python3 > "$ROOT/packages.txt"
  tar -czf "$HOME/uddns-validation-$(date -u +%Y%m%dT%H%M%SZ).tar.gz" -C "$HOME" uddns-results
  echo "Report is in HOME, not in uddns-results; review for secrets before sharing."
  ;;
*) echo "Usage: bash vm-test.sh {install|verify|update|backup|report}" >&2;exit 2;;
esac
