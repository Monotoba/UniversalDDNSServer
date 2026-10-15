import tempfile
import sqlite3
import unittest
from pathlib import Path

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.intents import PermissionDenied, UpdateConflict, UpdateState
from universalddns.orchestrator import UpdateOrchestrator
from universalddns.ports import BackendCapabilities


class Policy:
    allowed = True
    def may_update(self, principal_id, rrset):
        return self.allowed and principal_id == "client"


class Backend:
    capabilities = BackendCapabilities(frozenset({"A", "AAAA"}))
    def __init__(self):
        self.current = None
        self.calls = 0
        self.fail_after_commit = False

    def publish(self, rrset):
        self.calls += 1
        self.current = rrset
        if self.fail_after_commit:
            raise TimeoutError("reply lost")

    def observe(self, rrset):
        return self.current


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "journal.db"
        self.backend = Backend()
        self.policy = Policy()
        self.journal = SQLiteIntentJournal(self.path)
        self.svc = UpdateOrchestrator(self.policy, self.journal, self.backend)
        self.rr = RecordSet("example.org", "one.example.org", "A", 60, ("192.0.2.42",))

    def tearDown(self):
        self.journal.close()
        self.dir.cleanup()

    def test_idempotency_survives_restart(self):
        one = self.svc.submit("client", self.rr, "update-001")
        self.journal.close()
        self.journal = SQLiteIntentJournal(self.path)
        self.svc = UpdateOrchestrator(self.policy, self.journal, self.backend)
        two = self.svc.submit("client", self.rr, "update-001")
        self.assertEqual(one.identifier, two.identifier)
        with self.assertRaises(UpdateConflict):
            self.svc.submit("client", RecordSet(*self.rr.key, 60, ("192.0.2.43",)), "update-001")

    def test_lost_response_verified_without_republish(self):
        attempt = self.svc.submit("client", self.rr, "lost-response")
        self.backend.fail_after_commit = True
        with self.assertRaises(TimeoutError):
            self.svc.apply(attempt.identifier)
        self.assertEqual(self.svc.reconcile(attempt.identifier).state, UpdateState.APPLIED)
        self.assertEqual(self.backend.calls, 1)

    def test_interrupted_claim_reconciles_after_reopen(self):
        attempt = self.svc.submit("client", self.rr)
        self.journal.claim_with_lease(attempt.identifier)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE update_intents SET lease_expires_at=0 WHERE identifier=?", (attempt.identifier,))
        self.backend.current = self.rr
        self.journal.close()
        self.journal = SQLiteIntentJournal(self.path)
        self.svc = UpdateOrchestrator(self.policy, self.journal, self.backend)
        self.assertEqual(self.svc.reconcile(attempt.identifier).state, UpdateState.APPLIED)

    def test_mismatch_not_retried_without_explicit_request(self):
        attempt = self.svc.submit("client", self.rr)
        self.journal.claim_with_lease(attempt.identifier)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE update_intents SET lease_expires_at=0 WHERE identifier=?", (attempt.identifier,))
        self.assertEqual(self.svc.reconcile(attempt.identifier).state, UpdateState.APPLYING)
        self.assertEqual(self.backend.calls, 0)
        with self.assertRaises(UpdateConflict):
            self.svc.reconcile(attempt.identifier, retry=True)
        self.assertEqual(self.backend.calls, 0)
        self.assertEqual(self.journal.get(attempt.identifier).state, UpdateState.APPLYING)

    def test_revocation_prevents_retry(self):
        attempt = self.svc.submit("client", self.rr)
        self.backend.fail_after_commit = True
        with self.assertRaises(TimeoutError):
            self.svc.apply(attempt.identifier)
        self.backend.current = None  # authoritative mismatch after failed attempt
        self.policy.allowed = False
        with self.assertRaises(PermissionDenied):
            self.svc.reconcile(attempt.identifier, retry=True)
        self.assertEqual(self.backend.calls, 1)  # original failed attempt; no retry


    def test_invalid_key(self):
        with self.assertRaises(ValueError):
            self.svc.submit("client", self.rr, "invalid key")
