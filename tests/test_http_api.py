import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.http_api import APIPrincipal, create_app
from universalddns.orchestrator import UpdateOrchestrator
from universalddns.ports import BackendCapabilities


class Policy:
    def may_update(self, principal_id, rrset):
        return principal_id == "alice"


class Backend:
    capabilities = BackendCapabilities(frozenset({"A", "AAAA"}))
    def publish(self, rrset):
        raise AssertionError("HTTP must never publish DNS")


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "journal.db"
        def make_journal():
            return SQLiteIntentJournal(self.path)
        def make_orchestrator(journal):
            return UpdateOrchestrator(Policy(), journal, Backend())
        self.alice = "a" * 48
        self.bob = "b" * 48
        principals = (
            APIPrincipal.from_token("alice", self.alice,
                                    frozenset({"records:write", "intents:read"}),
                                    frozenset({"host"})),
            APIPrincipal.from_token("bob", self.bob, frozenset({"intents:read"}),
                                    frozenset({"host"})),
        )
        records = {"host": RecordSet("example.org", "host.example.org", "A",
                                     60, ("192.0.2.1",))}
        self.client = TestClient(create_app(make_journal, make_orchestrator,
                                            records, principals, rate_limit=20))
    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def auth(self, token):
        return {"Authorization": "Bearer " + token}

    def test_unauthenticated_and_scope(self):
        uri = "/api/v1/records/host/address"
        payload = {"address": "192.0.2.20", "request_id": "req-1"}
        self.assertEqual(self.client.put(uri, json=payload).status_code, 401)
        self.assertEqual(self.client.put(uri, json=payload, headers=self.auth(self.bob)).status_code, 403)

    def test_idempotence_owner_and_no_publication(self):
        url = "/api/v1/records/host/address"
        body = {"address": "192.0.2.20", "request_id": "repeat-1"}
        first = self.client.put(url, json=body, headers=self.auth(self.alice))
        self.assertEqual(first.status_code, 202)
        again = self.client.put(url, json=body, headers=self.auth(self.alice))
        self.assertEqual(first.json()["intent_id"], again.json()["intent_id"])
        identifier = first.json()["intent_id"]
        status_url = "/api/v1/intents/" + identifier
        self.assertEqual(self.client.get(status_url, headers=self.auth(self.alice)).json()["status"], "pending")
        self.assertEqual(self.client.get(status_url, headers=self.auth(self.bob)).status_code, 404)
        conflict = self.client.put(url, json={"address": "192.0.2.21", "request_id": "repeat-1"},
                                   headers=self.auth(self.alice))
        self.assertEqual(conflict.status_code, 409)

    def test_validates_mapping_and_address(self):
        url = "/api/v1/records/host/address"
        self.assertEqual(self.client.put(url, json={"address": "::1", "request_id": "v1"},
                                         headers=self.auth(self.alice)).status_code, 422)
        self.assertEqual(self.client.put("/api/v1/records/missing/address",
                                         json={"address": "192.0.2.1", "request_id": "v2"},
                                         headers=self.auth(self.alice)).status_code, 404)
