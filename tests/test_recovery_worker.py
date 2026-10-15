import sqlite3
import logging
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
                with self.assertLogs("universalddns.audit", logging.INFO) as captured:
                    self.assertEqual(worker.run_once().unresolved, 1)
                self.assertTrue(any("recovery_unresolved" in record for record in captured.output))
                self.assertTrue(any("recovery_batch_completed" in record for record in captured.output))
                self.assertEqual(backend.writes, 0)
                backend.observed = rrset
                self.assertEqual(worker.run_once().verified, 1)
                self.assertEqual(worker.run_once().inspected, 0)
                self.assertEqual(backend.writes, 0)

    def test_journal_batch_limits_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.db"
            with SQLiteIntentJournal(path) as journal:
                records = [RecordSet("example.org", f"node{index}.example.org", "A", 60,
                                     (f"192.0.2.{50 + index}",)) for index in range(3)]
                intents = [journal.enqueue("device", record) for record in records]
                self.assertEqual([i.identifier for i in journal.pending(limit=2)],
                                 [i.identifier for i in intents[:2]])
                self.assertEqual(len(journal.pending()), 3)
                for value in (0, -1, True, 1.5, 10001):
                    with self.subTest(value=value):
                        with self.assertRaises(ValueError):
                            journal.pending(limit=value)
                        with self.assertRaises(ValueError):
                            journal.expired_leases(limit=value)
                for intent in intents:
                    journal.claim_with_lease(intent.identifier)
                with sqlite3.connect(path) as db:
                    db.execute("UPDATE update_intents SET lease_expires_at=0")
                self.assertEqual(len(journal.expired_leases(limit=2)), 2)
                self.assertEqual(len(journal.expired_leases()), 3)
                backend = Backend()
                worker = RecoveryWorker(journal, UpdateOrchestrator(Allow(), journal, backend))
                self.assertEqual(worker.run_once(max_items=2).inspected, 2)
                self.assertEqual(worker.run_once(max_items=2).inspected, 2)
                self.assertEqual(backend.writes, 0)

    def test_batch_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteIntentJournal(Path(directory) / "journal.db") as journal:
                worker = RecoveryWorker(journal, UpdateOrchestrator(Allow(), journal, Backend()))
                with self.assertRaises(ValueError):
                    worker.run_once(max_items=0)
