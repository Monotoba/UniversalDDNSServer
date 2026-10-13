import sqlite3
import tempfile
import unittest
from pathlib import Path
from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.intents import UpdateConflict, UpdateState

class LeaseTests(unittest.TestCase):
    def test_expiration_fences_stale_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "data.db"
            with SQLiteIntentJournal(path) as a, SQLiteIntentJournal(path) as b:
                rr = RecordSet("example.org", "a.example.org", "A", 60, ("192.0.2.1",))
                job = a.enqueue("client", rr)
                token = a.claim_with_lease(job.identifier)
                self.assertIsNone(b.claim_with_lease(job.identifier))
                a.renew_lease(job.identifier, token)
                with sqlite3.connect(path) as db:
                    db.execute("UPDATE update_intents SET lease_expires_at=0")
                self.assertEqual(len(b.expired_leases()), 1)
                with self.assertRaises(UpdateConflict):
                    a.finish_owned(job.identifier, token, succeeded=True)
                self.assertEqual(b.get(job.identifier).state, UpdateState.APPLYING)
    def test_lease_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            with SQLiteIntentJournal(Path(temp) / "x.db") as db:
                job = db.enqueue("client", RecordSet("example.org", "x.example.org", "AAAA", 60, ("2001:db8::1",)))
                with self.assertRaises(ValueError):
                    db.claim_with_lease(job.identifier, lease_seconds=0)
                token = db.claim_with_lease(job.identifier)
                db.finish_owned(job.identifier, token, succeeded=True)
                self.assertEqual(db.get(job.identifier).state, UpdateState.APPLIED)
