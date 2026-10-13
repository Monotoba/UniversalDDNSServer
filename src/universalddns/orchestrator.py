"""Authorization-gated update submission and explicit reconciliation."""
from .domain import RecordSet
from .intents import PermissionDenied, UpdateConflict, UpdateState
from .ports import Authorizer, DNSBackend
from .adapters.sqlite_intents import SQLiteIntentJournal


class UpdateOrchestrator:
    def __init__(self, authorizer: Authorizer, journal: SQLiteIntentJournal, backend: DNSBackend):
        self._authorizer = authorizer
        self._journal = journal
        self._backend = backend

    def submit(self, principal_id: str, rrset: RecordSet, request_key: str | None = None):
        if not self._authorizer.may_update(principal_id, rrset):
            raise PermissionDenied("not permitted to update record")
        if rrset.record_type not in self._backend.capabilities.supported_record_types:
            raise ValueError("backend does not support record type")
        return self._journal.enqueue(principal_id, rrset, request_key=request_key)

    def apply(self, identifier: str):
        intent = self._journal.get(identifier)
        if not self._journal.claim(identifier):
            raise UpdateConflict("intent is not pending")
        try:
            self._backend.publish(intent.rrset)
        except Exception as exc:
            # An exception may represent an ambiguous remote result.
            self._journal.finish(identifier, succeeded=False, error=type(exc).__name__)
            raise
        else:
            self._journal.finish(identifier, succeeded=True)
        return self._journal.get(identifier)

    def reconcile(self, identifier: str, *, retry: bool = False):
        """Read authoritative RRset before resolving/retrying an uncertain attempt.

        Never interpret a failed observation as proof that the update was rejected.
        retry=True is an explicit operator decision; not an unattended retry loop.
        This presumes no independent writers modify the same RRset.
        """
        intent = self._journal.get(identifier)
        if intent.state not in (UpdateState.APPLYING, UpdateState.FAILED):
            raise UpdateConflict("only unresolved update attempts can be reconciled")
        observed = self._backend.observe(intent.rrset)  # type: ignore[attr-defined]
        if observed == intent.rrset:
            self._journal.mark_verified(identifier)
            return self._journal.get(identifier)
        if retry:
            if not self._authorizer.may_update(intent.principal_id, intent.rrset):
                raise PermissionDenied("permission revoked before retry")
            self._journal.requeue(identifier)
            return self.apply(identifier)
        return intent
