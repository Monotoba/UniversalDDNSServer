import tempfile
from pathlib import Path
import unittest

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.intents import PermissionDenied, UpdateConflict, UpdateState
from universalddns.orchestrator import UpdateOrchestrator
from universalddns.ports import BackendCapabilities

class Allow:
    def may_update(self, principal_id, rrset):
        return principal_id == "allowed" and rrset.zone == "example.org."

class Backend:
    capabilities = BackendCapabilities(frozenset({"A", "AAAA"}))
    def __init__(self):
        self.calls = []
        self.fail = False
    def publish(self, rrset):
        self.calls.append(rrset)
        if self.fail:
            raise TimeoutError("simulated")

class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "intents.db"
        self.journal = SQLiteIntentJournal(self.path)
        self.backend = Backend()
        self.svc = UpdateOrchestrator(Allow(), self.journal, self.backend)
        self.record = RecordSet("example.org","host.example.org","A",60,("192.0.2.15",))
    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()
    def test_authorization_precedes_write(self):
        with self.assertRaises(PermissionDenied):
            self.svc.submit("intruder", self.record)
        self.assertEqual(self.journal.pending(), ())
        self.assertEqual(self.backend.calls, [])
    def test_submit_and_apply(self):
        intent = self.svc.submit("allowed", self.record)
        self.assertEqual(intent.state, UpdateState.PENDING)
        result = self.svc.apply(intent.identifier)
        self.assertEqual(result.state, UpdateState.APPLIED)
        self.assertEqual(self.backend.calls, [self.record])
        with self.assertRaises(UpdateConflict):
            self.svc.apply(intent.identifier)
    def test_one_unfinished_update_per_record(self):
        self.svc.submit("allowed", self.record)
        with self.assertRaises(UpdateConflict):
            self.svc.submit("allowed", self.record)
    def test_failed_publisher_does_not_report_success(self):
        intent = self.svc.submit("allowed", self.record)
        self.backend.fail = True
        with self.assertRaises(TimeoutError):
            self.svc.apply(intent.identifier)
        self.assertEqual(self.journal.get(intent.identifier).state, UpdateState.FAILED)
    def test_pending_survives_restart(self):
        intent = self.svc.submit("allowed", self.record)
        self.journal.close()
        self.journal = SQLiteIntentJournal(self.path)
        self.assertEqual(self.journal.pending()[0].identifier, intent.identifier)
    def test_interrupted_requires_manual_reconciliation(self):
        intent = self.svc.submit("allowed", self.record)
        self.assertTrue(self.journal.claim(intent.identifier))
        self.assertEqual(self.journal.interrupted()[0].state, UpdateState.APPLYING)
        with self.assertRaises(UpdateConflict):
            self.svc.submit("allowed", self.record)
