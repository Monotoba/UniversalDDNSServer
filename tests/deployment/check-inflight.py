"""Deterministic crash-window simulation; isolated SQLite and fake authoritative DNS.

A backend publishes its RRset then raises a timeout before completion is
persisted. Recovery must observe the authoritative state, not publish twice.
This is not a kernel-level SIGKILL or real BIND network fault.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.orchestrator import UpdateOrchestrator


class Allow:
    def may_update(self, principal_id, rrset):
        return principal_id == "crash-fixture"


class Backend:
    def __init__(self):
        self.published = None
        self.writes = 0

    class Caps:
        supported_record_types = frozenset({"A", "AAAA"})

    capabilities = Caps()

    def publish(self, rrset):
        self.published = rrset
        self.writes += 1
        raise TimeoutError("simulated lost acknowledgement after DNS publication")

    def observe(self, rrset):
        return self.published if self.published == rrset else None


with TemporaryDirectory(prefix="uddns-inflight-") as temp:
    backend = Backend()
    rrset = RecordSet("lab.invalid", "inflight.lab.invalid", "A", 60, ("192.0.2.55",))
    path = Path(temp) / "intents.db"
    with SQLiteIntentJournal(path) as journal:
        orchestration = UpdateOrchestrator(Allow(), journal, backend)
        intent = orchestration.submit("crash-fixture", rrset, request_key="inflight-demo")
        try:
            orchestration.apply(intent.identifier)
        except TimeoutError:
            pass
        else:
            raise AssertionError("Simulated network timeout did not occur")
        assert backend.writes == 1
        assert journal.get(intent.identifier).state.value == "failed"
    # Reopen SQLite as if the worker had restarted.
    with SQLiteIntentJournal(path) as journal:
        resumed = UpdateOrchestrator(Allow(), journal, backend)
        result = resumed.reconcile(intent.identifier)
        assert result.state.value == "applied"
        assert backend.writes == 1, "Recovery incorrectly repeated DNS publication"
print("PASS: ambiguous post-publication timeout reconciled without duplicate write")
