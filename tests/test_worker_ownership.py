import tempfile
import sqlite3
import unittest
from pathlib import Path
from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.intents import UpdateConflict, UpdateState

class WorkerOwnershipTests(unittest.TestCase):
    def test_claim_and_stale_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.db"
            with SQLiteIntentJournal(path) as first, SQLiteIntentJournal(path) as second:
                rrset = RecordSet("example.org", "node.example.org", "A", 60, ("192.0.2.10",))
                intent = first.enqueue("client", rrset)
                first_token = first.claim_owned(intent.identifier)
                self.assertIsNotNone(first_token)
                self.assertIsNone(second.claim_owned(intent.identifier))
                with self.assertRaises(UpdateConflict):
                    second.finish_owned(intent.identifier, "wrong-token", succeeded=True)
                with sqlite3.connect(path) as db:
                    db.execute("UPDATE update_intents SET lease_expires_at=0 WHERE identifier=?", (intent.identifier,))
                first.requeue(intent.identifier)
                second_token = second.claim_owned(intent.identifier)
                self.assertNotEqual(first_token, second_token)
                with self.assertRaises(UpdateConflict):
                    first.finish_owned(intent.identifier, first_token, succeeded=True)
                second.finish_owned(intent.identifier, second_token, succeeded=True)
                self.assertEqual(first.get(intent.identifier).state, UpdateState.APPLIED)
