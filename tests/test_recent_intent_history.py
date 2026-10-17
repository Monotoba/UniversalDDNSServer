"""Recent history must be SQL-bounded by principal AND active scoped RRsets."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.http_api import APIPrincipal, create_app


class ScopedHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "journal.sqlite3"
        self.visible = RecordSet("example.org", "visible.example.org", "A",
                                 60, ("192.0.2.1",))
        self.hidden = RecordSet("example.org", "hidden.example.org", "A",
                                60, ("192.0.2.2",))
        self.records = {"visible": self.visible, "hidden": self.hidden}
        self.token = "a" * 40
        self.other_token = "b" * 40
        self.alice = APIPrincipal.from_token(
            "alice", self.token, frozenset({"intents:read"}),
            frozenset({"visible"}))
        self.bob = APIPrincipal.from_token(
            "bob", self.other_token, frozenset({"intents:read"}),
            frozenset({"visible", "hidden"}))
        self.reader = lambda: self.records
        def journal():
            return SQLiteIntentJournal(self.path)
        self.journal = journal
        def no_write(*_args):
            raise AssertionError("history must not mutate")
        self.client = TestClient(create_app(
            journal, no_write, self.records, (self.alice, self.bob),
            record_reader=lambda: self.reader()))
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer " + self.token}

    def test_history_is_scoped_before_limit_and_newest_first(self):
        with self.journal() as db:
            older = db.enqueue("alice", self.visible)
            # Finish original update so more rows can be queued for the RRset.
            lease = db.claim_with_lease(older.identifier)
            db.finish_owned(older.identifier, lease, succeeded=True)
            own_hidden = db.enqueue("alice", self.hidden)
            other = db.enqueue("bob", self.visible)
            bob_lease = db.claim_with_lease(other.identifier)
            db.finish_owned(other.identifier, bob_lease, succeeded=True)
            latest = db.enqueue("alice", self.visible)
        response = self.client.get("/api/v1/intents?limit=1", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["intents"][0]["intent_id"], latest.identifier)
        self.assertEqual(len(response.json()["intents"]), 1)
        response = self.client.get("/api/v1/intents?limit=20", headers=self.headers)
        ids = [v["intent_id"] for v in response.json()["intents"]]
        self.assertEqual(ids, [latest.identifier, older.identifier])
        self.assertNotIn(own_hidden.identifier, ids)
        self.assertNotIn(other.identifier, ids)
        self.assertEqual(response.json()["intents"][0]["record_id"], "visible")
        self.assertIn("created_at", response.json()["intents"][0])
        self.reader = lambda: {"hidden": self.hidden}
        self.assertEqual(self.client.get("/api/v1/intents",
                                        headers=self.headers).json(), {"intents": []})

    def test_auth_bounds_and_rejected_writes(self):
        self.assertEqual(self.client.get("/api/v1/intents").status_code, 401)
        for limit in ("0", "51", "-1", "invalid"):
            with self.subTest(limit=limit):
                self.assertEqual(self.client.get(
                    "/api/v1/intents?limit=" + limit,
                    headers=self.headers).status_code, 422)
        self.assertEqual(self.client.put(
            "/api/v1/records/visible/address", headers=self.headers,
            json={"address": "192.0.2.55", "request_id": "no-write"}
        ).status_code, 403)

    def test_journal_rejects_excessive_scoped_keys(self):
        with self.journal() as db:
            with self.assertRaises(ValueError):
                db.recent_for_principal(
                    "alice", tuple(("z", str(i), "A") for i in range(201)))
            self.assertEqual(db.recent_for_principal("alice", ()), ())


if __name__ == "__main__":
    unittest.main()
