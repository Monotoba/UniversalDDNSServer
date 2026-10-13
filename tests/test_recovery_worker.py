import sqlite3
import tempfile
import unittest
from pathlib import Path

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.orchestrator import UpdateOrchestrator
from universalddns.ports import BackendCapabilities
from universalddns.recovery_worker import RecoveryWorker


class Allow:
    def may_update(self, principal_id, rrset):
        return True


class Backend:
    capabilities = BackendCapabilities(frozenset({"A"}))

    def __init__(self):
        self.observed = None
        self.writes = 0

    def publish(self, rrset):
        self.writes += 1

    def observe(self, rrset):
        return self.observed


class RecoveryWorkerTests(unittest.TestCase):
    def test_only_expired_and_no_blind_republication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.db"
            backend = Backend()
            with SQLiteIntentJournal(path) as journal:
                service = UpdateOrchestrator(Allow(), journal, backend)
                rrset = RecordSet("example.org", "a.example.org", "A", 60, ("192.0.2.3",))
                intent = service.submit("device", rrset)
                journal.claim_with_lease(intent.identifier)
                worker = RecoveryWorker(journal, service)
                self.assertEqual(worker.run_once().inspected, 0)
                with sqlite3.connect(path) as db:
                    db.execute("UPDATE update_intents SET lease_expires_at=0")
                self.assertEqual(worker.run_once().unresolved, 1)
                self.assertEqual(backend.writes, 0)
                backend.observed = rrset
                self.assertEqual(worker.run_once().verified, 1)
                self.assertEqual(worker.run_once().inspected, 0)
                self.assertEqual(backend.writes, 0)

    def test_batch_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteIntentJournal(Path(directory) / "journal.db") as journal:
                worker = RecoveryWorker(journal, UpdateOrchestrator(Allow(), journal, Backend()))
                with self.assertRaises(ValueError):
                    worker.run_once(max_items=0)
