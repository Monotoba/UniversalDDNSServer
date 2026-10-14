"""Verify BIND refuses a TSIG-signed write outside the allowed test record.

Reads the local lab key without printing it. Never modifies a production zone.
"""
import subprocess
from pathlib import Path
import dns.name
import dns.query
import dns.rcode
import dns.resolver
import dns.tsigkeyring
import dns.update

config = Path("/etc/bind/named.conf.local").read_text()
expected = "update-policy { grant uddns-lab. name home.lab.invalid. A; };"
assert expected in config, "Installed BIND policy is not the expected restricted lab policy"
assert 'zone "lab.invalid"' in config, "Lab zone not detected"
assert subprocess.run(["systemd-detect-virt", "--vm"], capture_output=True).returncode == 0
assert subprocess.check_output(["hostname", "-s"], text=True).strip() == "uddns-prealpha"

key_config = Path("/etc/bind/uddns-lab.key").read_text()
import re
match = re.search(r'secret\s+"([^"]+)"', key_config)
assert match, "TSIG secret missing"
keyring = dns.tsigkeyring.from_text({"uddns-lab.": match.group(1)})
name = "disallowed-tsig-probe.lab.invalid."
resolver = dns.resolver.Resolver(configure=False)
resolver.nameservers = ["127.0.0.1"]
resolver.port = 53

def query_record():
    try:
        return {x.address for x in resolver.resolve(name, "A", search=False)}
    except dns.resolver.NXDOMAIN:
        return set()
    except dns.resolver.NoAnswer:
        return set()

assert not query_record(), "Test record already exists; refusing to modify"
update = dns.update.Update("lab.invalid.", keyring=keyring, keyname=dns.name.from_text("uddns-lab."), keyalgorithm="hmac-sha256")
update.replace("disallowed-tsig-probe", 60, "A", "192.0.2.99")
response = dns.query.tcp(update, "127.0.0.1", port=53, timeout=5)
assert response.rcode() == dns.rcode.REFUSED, (
    "Expected REFUSED for unauthorized name, received " + dns.rcode.to_text(response.rcode())
)
assert not query_record(), "Unauthorized DNS record was created"
print("PASS: BIND rejected unauthorized TSIG update with REFUSED; no record created")
