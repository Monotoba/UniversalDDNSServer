#!/usr/bin/env python3
"""Explicitly authorized live catalog->REST->worker->BIND disposable-VM test.

Requires a verified VM snapshot, operator DB write ACLs and a narrowly scoped
BIND policy for catalog-live.lab.invalid. Leaves the test DNS RRset in place.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

import dns.flags
import dns.message
import dns.query
import dns.rcode
import dns.rdatatype

from universalddns.local_operator import local_operator_identity
from universalddns.runtime import load_admin_settings
from universalddns.record_catalog import RecordCatalog

PYTHON = sys.executable
CONFIG = "/etc/universalddns/config.json"
RECORD_ID = "catalog-live-v04"
NAME = "catalog-live.lab.invalid."
ADDRESS = "192.0.2.73"


def cli(module, *args):
    p = subprocess.run([PYTHON, "-m", module, "--config", CONFIG, *args],
                       text=True, capture_output=True, check=False, timeout=20)
    if p.returncode:
        raise RuntimeError(f"{module} {args[0]} returned {p.returncode}: {p.stderr[:300]}")
    return p.stdout.strip()


def api(path, token, *, body=None, method="GET"):
    headers = {"Authorization": "Bearer " + token}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        "http://127.0.0.1:8765" + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return response.status, json.load(response)


def observed():
    response = dns.query.tcp(dns.message.make_query(NAME, "A"), "127.0.0.1", timeout=5)
    if not response.flags & dns.flags.AA or response.rcode() != dns.rcode.NOERROR:
        raise RuntimeError("authoritative DNS query failed")
    return {value.to_text() for answer in response.answer
            if answer.rdtype == dns.rdatatype.A and answer.name.to_text().lower() == NAME
            for value in answer}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-lab-write", action="store_true",
                        help="I verified VM snapshot, isolated test zone and BIND policy")
    args = parser.parse_args()
    if not args.confirm_lab_write:
        parser.error("explicit --confirm-lab-write required")
    if os.uname().nodename.split(".")[0] != "uddns-prealpha":
        parser.error("refusing unexpected hostname")
    if subprocess.run(["systemd-detect-virt", "--vm"], capture_output=True).returncode:
        parser.error("disposable VM required")
    operator = local_operator_identity()
    settings = load_admin_settings(CONFIG)
    if settings.zone != "lab.invalid." or settings.database.as_posix() != "/var/lib/universalddns/state.sqlite3":
        parser.error("unexpected lab zone or database path")
    if RECORD_ID in settings.records or any(x.name == NAME for x in settings.records.values()):
        parser.error("test identity collides with static configuration")
    with RecordCatalog(settings.database) as catalog:
        if catalog.get(RECORD_ID) is not None:
            parser.error("test record already exists; do not reuse old grants")
    if observed():
        parser.error("dedicated DNS name already has data; refusing overwrite")
    print(f"VM identity and dedicated lab name verified; local operator: {operator}", flush=True)
    # Publication test requires the pre-installed BIND update-policy to
    # explicitly permit this record; never amend BIND policy automatically.
    token = None
    revision = None
    try:
        created = json.loads(cli("universalddns.record_admin", "create", RECORD_ID,
                                 "--name", NAME, "--type", "A",
                                 "--ttl", "60", "--address", ADDRESS))
        revision = created["revision"]
        staged = json.loads(cli("universalddns.record_admin", "stage", RECORD_ID,
                                "--revision", str(revision), "--active", "yes"))
        revision = staged["revision"]
        token = cli("universalddns.admin", "issue",
                    "--principal", "catalog-live-verify",
                    "--record", RECORD_ID, "--scope", "records:write",
                    "--scope", "intents:read")
        status, found = api("/api/v1/records", token)
        assert status == 200 and any(row["id"] == RECORD_ID for row in found["records"])
        status, queued = api("/api/v1/records/" + RECORD_ID + "/address", token,
                             body={"address": ADDRESS, "request_id": "vm-" + uuid.uuid4().hex},
                             method="PUT")
        assert status == 202
        for _ in range(60):
            _, state = api("/api/v1/intents/" + queued["intent_id"], token)
            if state["status"] == "applied":
                break
            if state["status"] == "failed":
                raise RuntimeError("publishing worker failed; check BIND TSIG policy")
            time.sleep(0.5)
        else:
            raise RuntimeError("publishing worker timed out (30 seconds)")
        if observed() != {ADDRESS}:
            raise RuntimeError("authoritative DNS does not match published address")
        print("PASS: active catalog -> scoped REST -> worker -> authoritative BIND A")
    finally:
        # These operations may fail if the DB or CLI is unhealthy; inspect
        # blockers if cleanup cannot finish. Never emit the bearer token.
        if revision is not None:
            try:
                cli("universalddns.record_admin", "stage", RECORD_ID,
                    "--revision", str(revision), "--active", "no")
                print("Cleanup: record deactivated", flush=True)
            except Exception as exc:
                print(f"WARNING: deactivation failed: {exc}", file=sys.stderr)
        if token is not None:
            # Revoke by reference without passing the secret through argv.
            try:
                blocked = json.loads(cli("universalddns.record_admin",
                                         "blockers", RECORD_ID))
                for item in blocked["blocking_credentials"]:
                    if item["principal"] == "catalog-live-verify":
                        cli("universalddns.admin", "revoke-reference",
                            "--reference", item["reference"])
                print("Cleanup: test credential revoked", flush=True)
            except Exception as exc:
                print(f"WARNING: credential cleanup failed: {exc}", file=sys.stderr)
        token = None
        print("Note: DNS RRset and inactive catalog fixture remain; no DNS deletion.", flush=True)


if __name__ == "__main__":
    main()
