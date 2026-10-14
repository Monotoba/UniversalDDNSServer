"""VM-only pending-intent restart test; never stops the API or BIND."""
import json
import subprocess
import time
import uuid
import urllib.request
from pathlib import Path

import dns.resolver

TOKEN = Path.home() / ".uddns-vm-token"
assert TOKEN.is_file(), "VM test token missing"
token = TOKEN.read_text().strip()
headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
base = "http://127.0.0.1:8765"
body = json.dumps({
    "address": "192.0.2.43",
    "request_id": "restart-" + uuid.uuid4().hex,
}).encode()

def command(*args):
    subprocess.run(["sudo", "systemctl", *args, "universalddns-worker"], check=True)

def submit():
    req = urllib.request.Request(base + "/api/v1/records/home/address",
                                 data=body, headers=headers, method="PUT")
    with urllib.request.urlopen(req, timeout=8) as response:
        assert response.status == 202
        return json.load(response)["intent_id"]

def status(identifier):
    req = urllib.request.Request(base + "/api/v1/intents/" + identifier, headers=headers)
    with urllib.request.urlopen(req, timeout=8) as response:
        return json.load(response)["status"]

command("stop")
try:
    identifier = submit()
    assert submit() == identifier, "Idempotency replay created duplicate intent"
    assert status(identifier) == "pending", "Intent unexpectedly processed with worker stopped"
finally:
    command("start")
for _ in range(60):
    value = status(identifier)
    if value == "applied":
        break
    assert value != "failed", "Publication failed"
    time.sleep(0.5)
else:
    raise AssertionError("Pending intent not applied following worker restart")
resolver = dns.resolver.Resolver(configure=False)
resolver.nameservers = ["127.0.0.1"]
resolver.port = 53
assert {a.address for a in resolver.resolve("home.lab.invalid", "A")} == {"192.0.2.43"}
print("PASS: queued intent survived worker restart; idempotency and authoritative DNS verified")
