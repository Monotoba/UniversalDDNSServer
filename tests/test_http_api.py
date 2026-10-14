import tempfile
import base64
import threading
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.http_api import APIPrincipal, create_app
from universalddns.token_store import TokenStore
from universalddns.orchestrator import UpdateOrchestrator
from universalddns.ports import BackendCapabilities


class Policy:
    def may_update(self, principal_id, rrset):
        return principal_id == "alice"


class Backend:
    capabilities = BackendCapabilities(frozenset({"A", "AAAA"}))
    def publish(self, rrset):
        raise AssertionError("HTTP must never publish DNS")

    def observe(self, rrset):
        return None


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
                                            records, principals, rate_limit=20, dyndns_wait_seconds=0))
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


    def test_persistent_token_revocation_affects_existing_app(self):
        def principals():
            with TokenStore(self.path) as store:
                return store.principals()

        def journal():
            return SQLiteIntentJournal(self.path)

        def service(j):
            return UpdateOrchestrator(Policy(), j, Backend())

        with TokenStore(self.path) as store:
            token = store.issue("alice", frozenset({"records:write", "intents:read"}),
                                frozenset({"host"}))
        app = create_app(journal, service,
                         {"host": RecordSet("example.org", "host.example.org", "A",
                                            60, ("192.0.2.1",))}, principals)
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer " + token}
            self.assertEqual(client.put(
                "/api/v1/records/host/address", headers=headers,
                json={"address": "192.0.2.44", "request_id": "live-revoke"}
            ).status_code, 202)
            with TokenStore(self.path) as store:
                self.assertTrue(store.revoke(token))
            self.assertEqual(client.put(
                "/api/v1/records/host/address", headers=headers,
                json={"address": "192.0.2.44", "request_id": "another"}
            ).status_code, 401)


    def test_dyndns2_queues_without_publishing_and_denies_invalid_requests(self):
        def basic(token):
            encoded = base64.b64encode(("client:" + token).encode()).decode()
            return {"Authorization": "Basic " + encoded}

        url = "/nic/update"
        self.assertEqual("badauth\n", self.client.get(url).text)
        self.assertEqual("badauth\n", self.client.get(
            url, params={"hostname": "host.example.org", "myip": "192.0.2.20"},
            headers=basic("invalid")).text)
        self.assertEqual("nohost\n", self.client.get(
            url, params={"hostname": "other.example.org", "myip": "192.0.2.20"},
            headers=basic(self.alice)).text)
        self.assertEqual("dnserr\n", self.client.get(
            url, params={"hostname": "host.example.org", "myip": "::1"},
            headers=basic(self.alice)).text)
        response = self.client.get(
            url, params={"hostname": "host.example.org", "myip": "192.0.2.20"},
            headers=basic(self.alice))
        self.assertEqual(200, response.status_code)
        self.assertEqual("911\n", response.text)
        with SQLiteIntentJournal(self.path) as journal:
            intents = journal.list_by_state(("pending",), limit=10)
            self.assertEqual(1, len(intents))
            self.assertEqual(("192.0.2.20",), intents[0].rrset.values)


    def test_dyndns2_good_only_after_worker_records_applied(self):
        def journal():
            return SQLiteIntentJournal(self.path)

        def service(j):
            return UpdateOrchestrator(Policy(), j, Backend())

        principal = APIPrincipal.from_token(
            "alice", self.alice, frozenset({"records:write"}), frozenset({"host"})
        )
        app = create_app(journal, service,
                         {"host": RecordSet("example.org", "host.example.org", "A",
                                            60, ("192.0.2.1",))},
                         (principal,), dyndns_wait_seconds=2)
        def finish_from_worker():
            end = time.monotonic() + 1.5
            while time.monotonic() < end:
                with journal() as j:
                    pending = j.pending()
                    if pending:
                        token = j.claim_with_lease(pending[0].identifier)
                        if token:
                            j.finish_owned(pending[0].identifier, token, succeeded=True)
                            return
                time.sleep(0.02)

        worker = threading.Thread(target=finish_from_worker)
        worker.start()
        try:
            with TestClient(app) as client:
                header = base64.b64encode(("client:" + self.alice).encode()).decode()
                response = client.get("/nic/update",
                                      params={"hostname": "host.example.org",
                                              "myip": "192.0.2.88"},
                                      headers={"Authorization": "Basic " + header})
            self.assertEqual("good 192.0.2.88\n", response.text)
        finally:
            worker.join(timeout=3)

    def test_validates_mapping_and_address(self):
        url = "/api/v1/records/host/address"
        self.assertEqual(self.client.put(url, json={"address": "::1", "request_id": "v1"},
                                         headers=self.auth(self.alice)).status_code, 422)
        self.assertEqual(self.client.put("/api/v1/records/missing/address",
                                         json={"address": "192.0.2.1", "request_id": "v2"},
                                         headers=self.auth(self.alice)).status_code, 404)
