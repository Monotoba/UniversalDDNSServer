#!/usr/bin/env python3
"""Run real operator-gated CLI lifecycle against disposable SQLite/config only.

No installed service database, HTTP requests, TSIG network calls, or DNS writes.
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from universalddns.local_operator import local_operator_identity


def run(config: Path, *args: str, expected: int = 0) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "universalddns." + args[0],
         "--config", str(config), *args[1:]],
        capture_output=True, text=True, timeout=15, check=False,
    )
    if proc.returncode != expected:
        raise AssertionError(
            f"CLI command {args[0:2]!r} returned {proc.returncode}, "
            f"expected {expected}; stderr: {proc.stderr[:300]}"
        )
    return proc.stdout.strip()


def check() -> None:
    if os.uname().nodename.split(".")[0] != "uddns-prealpha":
        raise RuntimeError("refusing unexpected host")
    virtualized = subprocess.run(["systemd-detect-virt", "--vm"],
                                 capture_output=True, check=False)
    if virtualized.returncode:
        raise RuntimeError("disposable VM required")
    operator = local_operator_identity()
    with tempfile.TemporaryDirectory(prefix="uddns-operator-cli-") as tmp:
        root = Path(tmp)
        secret = root / "key.json"
        secret.write_text(json.dumps({
            "key_secret": base64.b64encode(bytes(32)).decode("ascii")
        }), encoding="utf-8")
        secret.chmod(0o600)
        config = root / "config.json"
        config.write_text(json.dumps({
            "database": str(root / "scratch.sqlite3"),
            "credentials": str(secret),
            "dns": {"zone": "lab.invalid", "server": "127.0.0.1",
                    "port": 53, "key_name": "uddns-lab."},
            "interval": 1,
            "records": {"home": {"name": "home.lab.invalid",
                                 "type": "A", "ttl": 60,
                                 "address": "192.0.2.1"}}
        }), encoding="utf-8")
        config.chmod(0o600)
        created = json.loads(run(config, "record_admin", "create", "candidate",
                                 "--name", "candidate.lab.invalid", "--type", "A",
                                 "--ttl", "60", "--address", "192.0.2.40"))
        assert created["revision"] == 1
        staged = json.loads(run(config, "record_admin", "stage", "candidate",
                                "--revision", "1", "--active", "yes"))
        assert staged["revision"] == 2
        token = run(config, "admin", "issue", "--principal", "fixture-client",
                    "--record", "candidate", "--scope", "records:write")
        assert len(token) >= 32
        try:
            inventory = json.loads(run(config, "admin", "list"))
            matches = [row for row in inventory if row["principal"] == "fixture-client"]
            assert len(matches) == 1
            reference = matches[0]["reference"]
            assert reference.startswith("cred-")
            disabled = json.loads(run(config, "record_admin", "stage", "candidate",
                                      "--revision", "2", "--active", "no"))
            assert disabled["revision"] == 3
            blocked = json.loads(run(config, "record_admin", "blockers", "candidate"))
            assert blocked["blocker_count"] == 1
            assert blocked["blocking_credentials"][0]["reference"] == reference
            run(config, "record_admin", "stage", "candidate",
                "--revision", "3", "--active", "yes", expected=4)
            assert run(config, "admin", "revoke-reference",
                       "--reference", reference) == "revoked"
            restored = json.loads(run(config, "record_admin", "stage", "candidate",
                                      "--revision", "3", "--active", "yes"))
            assert restored["revision"] == 4
            audit = json.loads(run(config, "admin", "history"))
            assert [event["action"] for event in audit[:2]] == ["revoked", "issued"]
            assert all(event["operator"] == operator for event in audit[:2])
            encoded = json.dumps(audit) + json.dumps(inventory)
            assert token not in encoded
        finally:
            token = None
    print("PASS: isolated operator CLI issue, block, revoke, reactivate and audit")


if __name__ == "__main__":
    check()
