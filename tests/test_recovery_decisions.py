"""Durable, non-authorizing operator decision records."""
import tempfile
import sqlite3
import unittest
from pathlib import Path

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.intents import UpdateConflict, UnknownIntent, UpdateState
from universalddns.recovery_decisions import RecoveryDecisionJournal


class RecoveryDecisionTests(unittest.TestCase):
    def test_persist_and_reject_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with SQLiteIntentJournal(path) as journal:
                intent = journal.enqueue("client", RecordSet(
                    "example.org", "home.example.org", "A", 60, ("192.0.2.17",)))
                with RecoveryDecisionJournal(path) as decisions:
                    decision_id = decisions.record(
                        intent_id=intent.identifier, expected_generation=0,
                        operator_id="maintainer", proposed_action="investigate",
                        observation="unknown", rationale="Review isolated workers")
                    self.assertEqual(len(decisions.list_for_intent(intent.identifier)), 1)
                    self.assertEqual(decisions.list_for_intent(intent.identifier)[0]["decision_id"],
                                     decision_id)
                    self.assertEqual(journal.get(intent.identifier).state, UpdateState.PENDING)
                    journal.claim_with_lease(intent.identifier)
                    with self.assertRaises(UpdateConflict):
                        decisions.record(
                            intent_id=intent.identifier, expected_generation=0,
                            operator_id="maintainer", proposed_action="propose_abandon",
                            observation="absent", rationale="Old snapshot")
            with RecoveryDecisionJournal(path) as reopened:
                self.assertEqual(len(reopened.list_for_intent(intent.identifier)), 1)

    def test_database_enforces_append_only_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with SQLiteIntentJournal(path) as journal:
                intent = journal.enqueue("client", RecordSet(
                    "example.org", "audit.example.org", "A", 60, ("192.0.2.24",)))
            with RecoveryDecisionJournal(path) as records:
                decision_id = records.record(
                    intent_id=intent.identifier, expected_generation=0,
                    operator_id="maintainer", proposed_action="investigate",
                    observation="unknown", rationale="Audit retention test")
            with sqlite3.connect(path) as db:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("UPDATE recovery_decisions SET rationale=? WHERE decision_id=?",
                               ("tampered", decision_id))
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("DELETE FROM recovery_decisions WHERE decision_id=?",
                               (decision_id,))
            with RecoveryDecisionJournal(path) as records:
                self.assertEqual(records.list_for_intent(intent.identifier)[0]["rationale"],
                                 "Audit retention test")

    def test_stale_proposal_rolls_back_and_allows_fresh_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with SQLiteIntentJournal(path) as journal:
                intent = journal.enqueue("client", RecordSet(
                    "example.org", "rollback.example.org", "A", 60, ("192.0.2.25",)))
                journal.claim_with_lease(intent.identifier)
            with RecoveryDecisionJournal(path) as records:
                with self.assertRaises(UpdateConflict):
                    records.record(intent_id=intent.identifier, expected_generation=0,
                                   operator_id="maintainer", proposed_action="investigate",
                                   observation="unknown", rationale="stale")
                records.record(intent_id=intent.identifier, expected_generation=1,
                               operator_id="maintainer", proposed_action="investigate",
                               observation="unknown", rationale="fresh")
                self.assertEqual(len(records.list_for_intent(intent.identifier)), 1)

    def test_validation_and_missing_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with SQLiteIntentJournal(path):
                pass
            defaults = dict(intent_id="missing", expected_generation=0,
                            operator_id="operator", proposed_action="investigate",
                            observation="unknown", rationale="Needs inspection")
            with RecoveryDecisionJournal(path) as decisions:
                with self.assertRaises(UnknownIntent):
                    decisions.record(**defaults)
                for overrides in (
                    {"expected_generation": True}, {"operator_id": "bad user"},
                    {"proposed_action": "force_retry"}, {"observation": "secret"},
                    {"rationale": ""}, {"rationale": "x" * 1001},
                ):
                    with self.subTest(overrides=overrides):
                        with self.assertRaises(ValueError):
                            decisions.record(**(defaults | overrides))
                with self.assertRaises(ValueError):
                    decisions.list_for_intent("missing", limit=0)
