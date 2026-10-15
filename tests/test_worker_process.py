import tempfile
import unittest
from threading import Event
from pathlib import Path
from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.orchestrator import UpdateOrchestrator
from universalddns.ports import BackendCapabilities
from universalddns.worker import PublicationWorker

class Allow:
    def may_update(self, principal_id, rrset):
        return True

class Backend:
    capabilities = BackendCapabilities(frozenset({"A"}))
    def __init__(self):
        self.writes = []
    def publish(self, rrset):
        self.writes.append(rrset)
    def observe(self, rrset):
        return self.writes[-1] if self.writes else None

class WorkerTests(unittest.TestCase):
    def test_stopped_poll_loop_does_not_process_work(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "data.db"
            backend = Backend()
            def journal_factory():
                return SQLiteIntentJournal(path)
            def service_factory(j):
                return UpdateOrchestrator(Allow(), j, backend)
            with journal_factory() as j:
                record = RecordSet("example.org", "stop.example.org", "A", 60,
                                   ("192.0.2.35",))
                service_factory(j).submit("client", record)
                stopped = Event()
                stopped.set()
                PublicationWorker(j, service_factory(j)).serve(
                    stopped, journal_factory, service_factory)
            self.assertEqual(backend.writes, [])


    def test_bounded_publication_keeps_remaining_pending(self):
        with tempfile.TemporaryDirectory() as d:
            with SQLiteIntentJournal(Path(d) / "data.db") as journal:
                backend = Backend()
                service = UpdateOrchestrator(Allow(), journal, backend)
                for index in range(3):
                    service.submit("client", RecordSet("example.org", f"node{index}.example.org", "A", 60,
                                                       (f"192.0.2.{40 + index}",)))
                worker = PublicationWorker(journal, service)
                self.assertEqual(worker.run_once(max_items=2).attempted, 2)
                self.assertEqual(len(journal.pending()), 1)
                self.assertEqual(worker.run_once(max_items=2).attempted, 1)
                self.assertEqual(len(journal.pending()), 0)
                self.assertEqual(len(backend.writes), 3)

    def test_only_pending_runs(self):
        with tempfile.TemporaryDirectory() as d:
            with SQLiteIntentJournal(Path(d) / "data.db") as j:
                backend = Backend()
                svc = UpdateOrchestrator(Allow(), j, backend)
                record = RecordSet("example.org", "host.example.org", "A", 60, ("192.0.2.30",))
                job = svc.submit("client", record)
                worker = PublicationWorker(j, svc)
                self.assertEqual(worker.run_once().applied, 1)
                self.assertEqual(worker.run_once().attempted, 0)
                self.assertEqual(j.get(job.identifier).state.value, "applied")
                self.assertEqual(backend.writes, [record])
