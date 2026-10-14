#!/usr/bin/env bash
# VM-only migration from the original wide test-zone TSIG grant.
set -Eeuo pipefail
[[ "$(hostname -s)" == "uddns-prealpha" ]] || { echo "Refusing unexpected host" >&2; exit 2; }
systemd-detect-virt --vm >/dev/null || { echo "Refusing non-VM system" >&2; exit 2; }
[[ "$(id -u)" == 0 ]] || { echo "Run with sudo" >&2; exit 2; }
CONF=/etc/bind/named.conf.local
OLD='update-policy { grant uddns-lab. zonesub A AAAA; };'
NEW='update-policy { grant uddns-lab. name home.lab.invalid. A; };'
test -f "$CONF"
python3 - "$CONF" "$OLD" "$NEW" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
old, new = sys.argv[2:]
data = p.read_text()
if data.count(new) == 1 and old not in data:
    print("Already restricted; no modification required")
elif data.count(old) == 1 and new not in data:
    p.with_suffix(".conf.local.prealpha-backup").write_text(data)
    p.write_text(data.replace(old, new))
    print("Restricted TSIG rule for lab fixture")
else:
    raise SystemExit("Unexpected policy; refusing automatic modification")
PY
if ! named-checkconf -z; then
  echo "BIND validation failed: restore backup manually before restart" >&2
  exit 1
fi
systemctl reload named
systemctl is-active --quiet named
grep -Fq "$NEW" "$CONF"
echo "PASS: BIND configuration grants lab TSIG only home.lab.invalid. A"
echo "IMPORTANT: Run vm-test.sh update to confirm actual publication after migration."
