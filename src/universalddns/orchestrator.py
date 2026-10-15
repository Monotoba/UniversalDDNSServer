"""Authorization-gated update submission and explicit reconciliation."""
from .audit import audit
from .domain import RecordSet
from .intents import PermissionDenied, UpdateConflict, UpdateState
from .ports import Authorizer, DNSBackend
from .adapters.sqlite_intents import SQLiteIntentJournal


class UpdateOrchestrator:
    def __init__(self, authorizer: Authorizer, journal: SQLiteIntentJournal, backend: DNSBackend, *, lease_seconds: int = 30):
        self._authorizer = authorizer
        self._journal = journal
        self._backend = backend
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError('invalid lease duration')
        self._lease_seconds = lease_seconds

    def is_current(self, principal_id: str, rrset: RecordSet) -> bool:
        """Read authoritative state for a scoped record; never write DNS."""
        if not self._authorizer.may_update(principal_id, rrset):
            raise PermissionDenied("not permitted to inspect record")
        return self._backend.observe(rrset) == rrset

    def submit(self, principal_id: str, rrset: RecordSet, request_key: str | None = None):
        if not self._authorizer.may_update(principal_id, rrset):
            raise PermissionDenied("not permitted to update record")
        if rrset.record_type not in self._backend.capabilities.supported_record_types:
            raise ValueError("backend does not support record type")
        return self._journal.enqueue(principal_id, rrset, request_key=request_key)

    def apply(self, identifier: str):
        intent = self._journal.get(identifier)
        token = self._journal.claim_with_lease(identifier, lease_seconds=self._lease_seconds)
        if token is None:
            audit("publication_claim_denied", intent=identifier)
            raise UpdateConflict("intent is not pending")
        audit("publication_started", intent=identifier)
        try:
            if not self._authorizer.may_update(intent.principal_id, intent.rrset):
                self._journal.finish_owned(identifier, token, succeeded=False,
                                           error="PermissionRevoked")
                audit("publication_denied", intent=identifier, reason="permission_revoked")
                raise PermissionDenied("permission revoked before publication")
            self._backend.publish(intent.rrset)
        except PermissionDenied:
            raise
        except Exception as exc:
            # An exception may represent an ambiguous remote result.
            self._journal.finish_owned(identifier, token, succeeded=False, error=type(exc).__name__)
            audit("publication_failed", intent=identifier, error=type(exc).__name__)
            raise
        else:
            self._journal.finish_owned(identifier, token, succeeded=True)
            audit("publication_applied", intent=identifier)
        return self._journal.get(identifier)

    def assess_recovery(self, identifier: str) -> dict[str, object]:
        """Read-only recovery assessment; never retries or updates intent state.

        Observation may race an outstanding DNS write, so a mismatch is not
        evidence that replay is safe.
        """
        intent = self._journal.get(identifier)
        if intent.state not in (UpdateState.APPLYING, UpdateState.FAILED):
            raise UpdateConflict("only unresolved attempts can be assessed")
        audit("operator_recovery_assessment_started", intent=identifier)
        try:
            observed = self._backend.observe(intent.rrset)
        except Exception as exc:
            audit("operator_recovery_assessment_error", intent=identifier,
                  error=type(exc).__name__)
            raise
        matches = observed == intent.rrset
        audit("operator_recovery_assessment_completed", intent=identifier,
              state=intent.state.value, matches=str(matches).lower())
        return {
            "intent_id": identifier,
            "state": intent.state.value,
            "authoritative_match": matches,
            "observation": ("matches" if matches else
                            "absent" if observed is None else "differs"),
            "next_action": ("reconcile_when_eligible" if matches else
                            "isolate_workers_and_investigate"),
            "retry_safe": False,
        }

    def reconcile(self, identifier: str, *, retry: bool = False):
        """Read authoritative RRset before resolving/retrying an uncertain attempt.

        Never interpret a failed observation as proof that the update was rejected.
        retry=True is an explicit operator decision; not an unattended retry loop.
        This presumes no independent writers modify the same RRset.
        """
        intent = self._journal.get(identifier)
        if intent.state not in (UpdateState.APPLYING, UpdateState.FAILED):
            raise UpdateConflict("only unresolved update attempts can be reconciled")
        audit("reconciliation_started", intent=identifier)
        observed = self._backend.observe(intent.rrset)  # type: ignore[attr-defined]
        if observed == intent.rrset:
            self._journal.mark_verified(identifier)
            audit("reconciliation_verified", intent=identifier)
            return self._journal.get(identifier)
        if retry:
            # An expired lease does not cancel a DNS request already in flight.
            # Requeuing an APPLYING intent could race with that original write.
            if intent.state is UpdateState.APPLYING:
                raise UpdateConflict("in-flight publication cannot be safely retried")
            if not self._authorizer.may_update(intent.principal_id, intent.rrset):
                raise PermissionDenied("permission revoked before retry")
            audit("reconciliation_retry_requested", intent=identifier)
            self._journal.requeue(identifier)
            return self.apply(identifier)
        audit("reconciliation_unresolved", intent=identifier)
        return intent
