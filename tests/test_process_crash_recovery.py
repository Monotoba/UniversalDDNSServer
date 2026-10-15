"""Real subprocess death during publication, with durable SQLite recovery."""

import os
import signal
import sqlite3
import subprocess
import sys
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


class ObservingBackend:
    capabilities = BackendCapabilities(frozenset({"A"}))

    def __init__(self, marker):
        self.marker = marker
        self.writes = 0

    def publish(self, rrset):
        self.writes += 1
        raise AssertionError("recovery must never republish")

    def observe(self, rrset):
        return rrset if self.marker.exists() else None


# Separate interpreter and SQLite connection; process is killed inside publish().
CHILD = """
import os
import signal
import sys
from pathlib import Path
from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.orchestrator import UpdateOrchestrator
from universalddns.ports import BackendCapabilities

class Allow:
    def may_update(self, principal_id, rrset):
        return True

class Backend:
    capabilities = BackendCapabilities(frozenset({"A"}))

    def publish(self, rrset):
        Path(sys.argv[3]).write_text("accepted", encoding="utf-8")
        os.kill(os.getpid(), signal.SIGKILL)

    def observe(self, rrset):
        return None

with SQLiteIntentJournal(sys.argv[1]) as journal:
    service = UpdateOrchestrator(Allow(), journal, Backend())
    service.apply(sys.argv[2])
"""


@unittest.skipUnless(os.name == "posix" and hasattr(signal, "SIGKILL"),
                     "requires POSIX SIGKILL")
class ProcessCrashRecoveryTests(unittest.TestCase):
    def test_sigkill_after_backend_acceptance_is_reconciled_without_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "journal.db"
            marker = Path(directory) / "accepted"
            rrset = RecordSet("example.org", "killed.example.org", "A", 60,
                              ("192.0.2.81",))
            with SQLiteIntentJournal(db_path) as journal:
                intent = journal.enqueue("device", rrset)

            process = subprocess.run(
                [sys.executable, "-c", CHILD, str(db_path),
                 intent.identifier, str(marker)],
                check=False, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(process.returncode, -signal.SIGKILL, process.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "accepted")

            backend = ObservingBackend(marker)
            with SQLiteIntentJournal(db_path) as journal:
                self.assertEqual(journal.get(intent.identifier).state.value, "applying")
                recovery = RecoveryWorker(journal, UpdateOrchestrator(Allow(), journal, backend))
                # A fresh worker must not interfere before the lease expires.
                self.assertEqual(recovery.run_once().inspected, 0)
                with sqlite3.connect(db_path) as db:
                    db.execute(
                        "UPDATE update_intents SET lease_expires_at=0 WHERE identifier=?",
                        (intent.identifier,),
                    )
                report = recovery.run_once()
                self.assertEqual((report.inspected, report.verified, report.errors),
                                 (1, 1, 0))
                self.assertEqual(journal.get(intent.identifier).state.value, "applied")
                self.assertEqual(backend.writes, 0)
                self.assertEqual(recovery.run_once().inspected, 0)

    def test_sigkill_without_confirmation_keeps_intent_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "journal.db"
            marker = Path(directory) / "accepted"
            rrset = RecordSet("example.org", "uncertain-kill.example.org", "A", 60,
                              ("192.0.2.82",))
            with SQLiteIntentJournal(db_path) as journal:
                intent = journal.enqueue("device", rrset)

            process = subprocess.run(
                [sys.executable, "-c", CHILD, str(db_path),
                 intent.identifier, str(marker)],
                check=False, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(process.returncode, -signal.SIGKILL, process.stderr)
            marker.unlink()  # authoritative observation does not confirm the write
            backend = ObservingBackend(marker)
            with SQLiteIntentJournal(db_path) as journal:
                with sqlite3.connect(db_path) as db:
                    db.execute(
                        "UPDATE update_intents SET lease_expires_at=0 WHERE identifier=?",
                        (intent.identifier,),
                    )
                report = RecoveryWorker(
                    journal, UpdateOrchestrator(Allow(), journal, backend)
                ).run_once()
                self.assertEqual((report.inspected, report.unresolved, report.errors),
                                 (1, 1, 0))
                self.assertEqual(journal.get(intent.identifier).state.value, "applying")
                self.assertEqual(backend.writes, 0)
