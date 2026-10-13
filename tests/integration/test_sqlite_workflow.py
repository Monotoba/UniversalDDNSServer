"""End-to-end integration of real SQLite journal and fake DNS publishing port.

This is not an authoritative DNS/BIND integration test.
"""
import tempfile
import unittest
from pathlib import Path

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.intents import UpdateConflict, UpdateState
from universalddns.orchestrator import UpdateOrchestrator
from universalddns.ports import BackendCapabilities


class AllowRecord:
    def may_update(self, principal_id, rrset):
        return principal_id == "station-1" and rrset.name == "station.example.org."


class RecordingBackend:
    capabilities = BackendCapabilities(frozenset({"A", "AAAA"}))

    def __init__(self):
        self.records = []

    def publish(self, rrset):
        self.records.append(rrset)


class SQLiteWorkflowIntegrationTests(unittest.TestCase):
    def test_pending_persists_restart_and_publishes_once(self):
        rrset = RecordSet("example.org", "station.example.org", "A", 60, ("192.0.2.8",))
        backend = RecordingBackend()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intents.sqlite"
            with SQLiteIntentJournal(path) as journal:
                first = UpdateOrchestrator(AllowRecord(), journal, backend).submit(
                    "station-1", rrset
                )
                self.assertEqual(first.state, UpdateState.PENDING)
            with SQLiteIntentJournal(path) as journal:
                service = UpdateOrchestrator(AllowRecord(), journal, backend)
                self.assertEqual(journal.pending()[0].identifier, first.identifier)
                self.assertEqual(service.apply(first.identifier).state, UpdateState.APPLIED)
                with self.assertRaises(UpdateConflict):
                    service.apply(first.identifier)
                self.assertEqual(backend.records, [rrset])
            with SQLiteIntentJournal(path) as journal:
                self.assertEqual(journal.get(first.identifier).state, UpdateState.APPLIED)
