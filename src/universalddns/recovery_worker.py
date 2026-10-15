"""Bounded reconciliation pass; never blindly repeats ambiguous DNS writes."""
from dataclasses import dataclass

from .audit import audit
from .adapters.sqlite_intents import SQLiteIntentJournal
from .orchestrator import UpdateOrchestrator


@dataclass(frozen=True)
class RecoveryReport:
    inspected: int
    verified: int
    unresolved: int
    errors: int


class RecoveryWorker:
    """Runs an explicit recovery pass; has no network-write retry loop."""

    def __init__(self, journal: SQLiteIntentJournal, orchestrator: UpdateOrchestrator):
        self._journal = journal
        self._orchestrator = orchestrator

    def run_once(self, *, max_items: int = 100) -> RecoveryReport:
        if type(max_items) is not int or not 1 <= max_items <= 10000:
            raise ValueError("invalid reconciliation batch size")
        attempts = self._journal.expired_leases(limit=max_items)
        verified = 0
        unresolved = 0
        errors = 0
        for intent in attempts:
            try:
                result = self._orchestrator.reconcile(intent.identifier)
            except Exception as exc:
                # Preserve ambiguity if the server cannot be observed or ownership changed.
                errors += 1
                audit("recovery_observation_failed", intent=intent.identifier,
                      error=type(exc).__name__)
            else:
                if result.state.value == "applied":
                    verified += 1
                else:
                    unresolved += 1
                    audit("recovery_unresolved", intent=intent.identifier)
        if attempts:
            audit("recovery_batch_completed", inspected=str(len(attempts)),
                  verified=str(verified), unresolved=str(unresolved), errors=str(errors))
        return RecoveryReport(len(attempts), verified, unresolved, errors)
