import sqlite3
import tempfile
import unittest
from pathlib import Path
from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.intents import UpdateConflict, UpdateState, UnknownIntent

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

    def test_generation_tracks_transitions_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "data.db"
            with SQLiteIntentJournal(path) as journal:
                record = RecordSet("example.org", "generation.example.org",
                                   "A", 60, ("192.0.2.20",))
                intent = journal.enqueue("client", record)
                self.assertEqual(journal.generation(intent.identifier), 0)
                token = journal.claim_with_lease(intent.identifier)
                self.assertEqual(journal.generation(intent.identifier), 1)
                journal.renew_lease(intent.identifier, token)
                self.assertEqual(journal.generation(intent.identifier), 2)
                journal.finish_owned(intent.identifier, token, succeeded=True)
                self.assertEqual(journal.generation(intent.identifier), 3)
            with SQLiteIntentJournal(path) as reopened:
                self.assertEqual(reopened.generation(intent.identifier), 3)
                with self.assertRaises(UpdateConflict):
                    reopened.finish_owned(intent.identifier, token, succeeded=True)

    def test_generation_migrates_legacy_database(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "old.db"
            with sqlite3.connect(path) as db:
                db.execute("""CREATE TABLE update_intents (
                    identifier TEXT PRIMARY KEY, principal_id TEXT NOT NULL,
                    zone TEXT NOT NULL, name TEXT NOT NULL,
                    record_type TEXT NOT NULL, ttl INTEGER NOT NULL,
                    values_json TEXT NOT NULL, state TEXT NOT NULL, error TEXT,
                    request_key TEXT, owner_token TEXT, lease_expires_at INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )""")
            with SQLiteIntentJournal(path) as journal:
                record = RecordSet("example.org", "legacy.example.org",
                                   "A", 60, ("192.0.2.21",))
                intent = journal.enqueue("client", record)
                self.assertEqual(journal.generation(intent.identifier), 0)
                self.assertEqual(journal.generation(intent.identifier), 0)
                with self.assertRaises(UnknownIntent):
                    journal.generation("missing")

    def test_legacy_unfenced_transitions_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with SQLiteIntentJournal(Path(temp) / "x.db") as db:
                job = db.enqueue("client", RecordSet("example.org", "x.example.org", "A", 60, ("192.0.2.1",)))
                with self.assertRaises(UpdateConflict):
                    db.claim(job.identifier)
                token = db.claim_with_lease(job.identifier)
                with self.assertRaises(UpdateConflict):
                    db.finish(job.identifier, succeeded=True)
                with self.assertRaises(UpdateConflict):
                    db.requeue(job.identifier)
                with self.assertRaises(UpdateConflict):
                    db.mark_verified(job.identifier)
                db.finish_owned(job.identifier, token, succeeded=True)
