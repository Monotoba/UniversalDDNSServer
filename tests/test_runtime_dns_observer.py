"""Prove API runtime wires only authoritative observation into record details."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from universalddns.domain import RecordSet
from universalddns.http_api import APIPrincipal, create_app
from universalddns import runtime


class RuntimeAuthoritativeObserverTests(unittest.TestCase):
    def test_runtime_wires_read_only_backend_observer(self):
        rrset = RecordSet("example.org", "host.example.org", "A", 60,
                          ("192.0.2.5",))
        token = "u" * 40
        principal = APIPrincipal.from_token(
            "viewer", token, frozenset({"intents:read"}), frozenset({"host"}))
        settings = SimpleNamespace(database=Path("/unused"), records={"host": rrset},
                                   dns=object())
        calls = []

        class Backend:
            def __init__(self, config):
                self.assertion = config
            def observe(self, record):
                calls.append(("observe", record))
                return record
            def publish(self, record):
                raise AssertionError("dashboard must never publish")

        class Catalog:
            def __init__(self, _path):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return None

        def journal():
            raise AssertionError("record details must not use journal")
        def orchestrator(_instance):
            raise AssertionError("record details must not instantiate publisher")

        with patch.dict(os.environ, {"UNIVERSALDDNS_CONFIG": "/unused"}), \\
             patch.object(runtime, "load_settings", return_value=settings), \\
             patch.object(runtime, "RecordCatalog", Catalog), \\
             patch.object(runtime, "factories", return_value=(journal, orchestrator, lambda: (principal,))), \\
             patch.object(runtime, "catalog_snapshot", return_value=({"host": rrset}, (principal,))), \\
             patch.object(runtime, "RFC2136Backend", Backend):
            app = runtime.api_app()
        with TestClient(app) as client:
            response = client.get("/api/v1/records/host",
                                  headers={"Authorization": "Bearer " + token})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["authoritative"]["status"], "matches_template")
            self.assertEqual(calls, [("observe", rrset)])
            self.assertEqual(client.get("/api/v1/records/host").status_code, 401)

    def test_runtime_observer_failure_does_not_claim_absence(self):
        rrset = RecordSet("example.org", "host.example.org", "A", 60,
                          ("192.0.2.5",))
        token = "v" * 40
        principal = APIPrincipal.from_token(
            "viewer", token, frozenset({"intents:read"}), frozenset({"host"}))
        def observe(_record):
            raise TimeoutError("upstream unavailable")
        app = create_app(lambda: None, lambda _j: None, {"host": rrset},
                         (principal,), record_observer=observe)
        with TestClient(app) as client:
            response = client.get("/api/v1/records/host",
                                  headers={"Authorization": "Bearer " + token})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["authoritative"]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
