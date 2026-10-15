"""One bounded publish pass, independent of the HTTP request lifecycle."""
from dataclasses import dataclass
from .adapters.sqlite_intents import SQLiteIntentJournal
from .orchestrator import UpdateOrchestrator
from .recovery_worker import RecoveryWorker

@dataclass(frozen=True)
class WorkerReport:
    attempted: int
    applied: int
    errors: int
    reconciled: int

class PublicationWorker:
    def __init__(self, journal: SQLiteIntentJournal, orchestrator: UpdateOrchestrator):
        self.journal = journal
        self.orchestrator = orchestrator

    def run_once(self, *, max_items: int = 100) -> WorkerReport:
        if type(max_items) is not int or not 1 <= max_items <= 10000:
            raise ValueError("invalid batch size")
        recovery = RecoveryWorker(self.journal, self.orchestrator).run_once(max_items=max_items)
        pending = self.journal.pending(limit=max_items)
        applied = errors = 0
        for intent in pending:
            try:
                self.orchestrator.apply(intent.identifier)
                applied += 1
            except Exception:
                errors += 1
        return WorkerReport(len(pending), applied, errors, recovery.verified)

    def serve(self, stop_event, journal_factory, orchestrator_factory, *,
              interval_seconds: float = 2.0, max_items: int = 100):
        """Cooperative poll loop with separate SQLite connection per cycle.

        The event is checked between cycles. In-flight DNS queries use backend
        timeouts and cannot be interrupted by the stop signal.
        """
        if not 0.1 <= interval_seconds <= 3600:
            raise ValueError("invalid polling interval")
        while not stop_event.is_set():
            with journal_factory() as journal:
                orchestrator = orchestrator_factory(journal)
                PublicationWorker(journal, orchestrator).run_once(max_items=max_items)
            stop_event.wait(interval_seconds)
