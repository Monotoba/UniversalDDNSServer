"""Authorization-gated update submission and explicit backend processing."""
from .domain import RecordSet
from .intents import PermissionDenied, UpdateConflict
from .ports import Authorizer, DNSBackend
from .adapters.sqlite_intents import SQLiteIntentJournal

class UpdateOrchestrator:
    def __init__(self, authorizer: Authorizer, journal: SQLiteIntentJournal, backend: DNSBackend):
        self._authorizer = authorizer
        self._journal = journal
        self._backend = backend

    def submit(self, principal_id: str, rrset: RecordSet):
        if not self._authorizer.may_update(principal_id, rrset):
            raise PermissionDenied("not permitted to update record")
        if rrset.record_type not in self._backend.capabilities.supported_record_types:
            raise ValueError("backend does not support record type")
        return self._journal.enqueue(principal_id, rrset)

    def apply(self, identifier: str):
        # All network calls are deliberately outside SQLite transactions.
        intent = self._journal.get(identifier)
        if not self._journal.claim(identifier):
            raise UpdateConflict("intent is not pending")
        try:
            self._backend.publish(intent.rrset)
        except Exception as exc:
            self._journal.finish(identifier, succeeded=False, error=type(exc).__name__)
            raise
        else:
            self._journal.finish(identifier, succeeded=True)
        return self._journal.get(identifier)
