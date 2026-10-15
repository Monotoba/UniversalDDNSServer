import sqlite3
import logging
import tempfile
import unittest
from pathlib import Path

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.intents import UpdateConflict
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

    def test_process_termination_after_publication_reconciles_without_rewrite(self):
        """Simulate termination after backend acceptance but before journal completion."""
        class TerminatingBackend(Backend):
            def publish(self, rrset):
                self.writes += 1
                self.observed = rrset
                raise SystemExit("simulated worker termination after DNS publication")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.db"
            backend = TerminatingBackend()
            with SQLiteIntentJournal(path) as journal:
                service = UpdateOrchestrator(Allow(), journal, backend)
                rrset = RecordSet("example.org", "crash.example.org", "A", 60,
                                  ("192.0.2.70",))
                intent = service.submit("device", rrset)
                with self.assertRaises(SystemExit):
                    service.apply(intent.identifier)
                self.assertEqual(journal.get(intent.identifier).state.value, "applying")
                self.assertEqual(backend.writes, 1)
            # Reopening SQLite models a restarted worker with no in-memory state.
            with SQLiteIntentJournal(path) as journal:
                service = UpdateOrchestrator(Allow(), journal, backend)
                worker = RecoveryWorker(journal, service)
                self.assertEqual(worker.run_once().inspected, 0)
                with sqlite3.connect(path) as db:
                    db.execute("UPDATE update_intents SET lease_expires_at=0 WHERE identifier=?",
                               (intent.identifier,))
                report = worker.run_once()
                self.assertEqual((report.inspected, report.verified, report.errors), (1, 1, 0))
                self.assertEqual(journal.get(intent.identifier).state.value, "applied")
                self.assertEqual(backend.writes, 1)
                self.assertEqual(worker.run_once().inspected, 0)

    def test_process_termination_with_unconfirmed_dns_preserves_ambiguity(self):
        """An expired lease must not trigger a replay when observation disagrees."""
        class TerminatingBackend(Backend):
            def publish(self, rrset):
                self.writes += 1
                raise SystemExit("simulated termination before confirmation")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.db"
            backend = TerminatingBackend()
            with SQLiteIntentJournal(path) as journal:
                service = UpdateOrchestrator(Allow(), journal, backend)
                intent = service.submit(
                    "device", RecordSet("example.org", "uncertain.example.org", "A", 60,
                                        ("192.0.2.71",)))
                with self.assertRaises(SystemExit):
                    service.apply(intent.identifier)
            with SQLiteIntentJournal(path) as journal:
                with sqlite3.connect(path) as db:
                    db.execute("UPDATE update_intents SET lease_expires_at=0 WHERE identifier=?",
                               (intent.identifier,))
                worker = RecoveryWorker(journal, UpdateOrchestrator(Allow(), journal, backend))
                report = worker.run_once()
                self.assertEqual((report.inspected, report.unresolved, report.errors), (1, 1, 0))
                self.assertEqual(journal.get(intent.identifier).state.value, "applying")
                self.assertEqual(backend.writes, 1)

    def test_expired_applying_retry_is_rejected_even_when_dns_mismatches(self):
        """Lease expiry never proves the old DNS request stopped executing."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.db"
            backend = Backend()
            with SQLiteIntentJournal(path) as journal:
                service = UpdateOrchestrator(Allow(), journal, backend)
                rrset = RecordSet("example.org", "racing.example.org", "A", 60,
                                  ("192.0.2.92",))
                intent = service.submit("device", rrset)
                journal.claim_with_lease(intent.identifier)
                with sqlite3.connect(path) as db:
                    db.execute("UPDATE update_intents SET lease_expires_at=0 WHERE identifier=?",
                               (intent.identifier,))
                with self.assertRaisesRegex(UpdateConflict, "in-flight publication"):
                    service.reconcile(intent.identifier, retry=True)
                self.assertEqual(journal.get(intent.identifier).state.value, "applying")
                self.assertEqual(backend.writes, 0)
                backend.observed = rrset
                self.assertEqual(service.reconcile(intent.identifier, retry=True).state.value,
                                 "applied")
                self.assertEqual(backend.writes, 0)

    def test_batch_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            with SQLiteIntentJournal(Path(directory) / "journal.db") as journal:
                worker = RecoveryWorker(journal, UpdateOrchestrator(Allow(), journal, Backend()))
                with self.assertRaises(ValueError):
                    worker.run_once(max_items=0)
