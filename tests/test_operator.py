"""Local operator inspection behavior is bounded and read-only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.intents import UpdateConflict, UnknownIntent

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.operator import describe, main


class OperatorInspectionTests(unittest.TestCase):
    def test_list_show_and_state_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SQLiteIntentJournal(Path(tmp) / "state.db") as journal:
                rrset = RecordSet("lab.invalid", "home.lab.invalid", "A", 60,
                                  ("192.0.2.19",))
                intent = journal.enqueue("demo-principal", rrset)
                results = journal.list_by_state(("pending",), limit=1)
                self.assertEqual([intent.identifier], [item.identifier for item in results])
                self.assertEqual("pending", describe(results[0])["state"])
                self.assertEqual((), journal.list_by_state(("failed",)))
                with self.assertRaises(ValueError):
                    journal.list_by_state(("pending'); DROP TABLE update_intents; --",))
                with self.assertRaises(ValueError):
                    journal.list_by_state(("pending",), limit=0)
                self.assertIsNotNone(journal.get(intent.identifier))


    def test_cli_returns_specific_exit_codes(self):
        class Journal:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def get(self, identifier):
                raise UnknownIntent(identifier)

        argv = ["uddns-operator", "--config", "test-config", "show", "missing"]
        with (patch("sys.argv", argv), patch("universalddns.operator.load_settings"), patch("universalddns.operator.factories", return_value=(Journal, None, None))):
            self.assertEqual(3, main())

        class ConflictJournal(Journal):
            def get(self, identifier):
                raise UpdateConflict("unresolved")

        with (patch("sys.argv", argv), patch("universalddns.operator.load_settings"), patch("universalddns.operator.factories", return_value=(ConflictJournal, None, None))):
            self.assertEqual(4, main())


    def test_cli_assessment_is_read_only(self):
        class Journal:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        class Service:
            def assess_recovery(self, identifier):
                self.identifier = identifier
                return {"intent_id": identifier, "state": "applying",
                        "authoritative_match": False, "retry_safe": False,
                        "next_action": "isolate_workers_and_investigate"}

        service = Service()
        argv = ["operator", "--config", "test-config", "assess", "intent-id"]
        with (patch("sys.argv", argv),
              patch("universalddns.operator.load_settings"),
              patch("universalddns.operator.factories",
                    return_value=(Journal, lambda _: service, None))):
            self.assertEqual(main(), 0)
        self.assertEqual(service.identifier, "intent-id")

    def test_proposal_cli_uses_os_identity_not_caller_override(self):
        from unittest.mock import MagicMock
        rrset = RecordSet("lab.invalid", "home.lab.invalid", "A", 60,
                          ("192.0.2.19",))
        from universalddns.intents import UpdateIntent, UpdateState

        class Journal:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def get(self, identifier):
                return UpdateIntent(identifier, "client", rrset, UpdateState.APPLYING)

        decision_store = MagicMock()
        decision_store.__enter__.return_value = decision_store
        decision_store.record.return_value = "proposal-id"
        settings = MagicMock(database="test.db")
        argv = ["operator", "--config", "test-config", "propose", "intent-id",
                "--generation", "3", "--action", "investigate",
                "--observation", "unknown", "--rationale", "review worker"]
        with (patch("sys.argv", argv),
              patch("universalddns.operator.load_settings", return_value=settings),
              patch("universalddns.operator.factories",
                    return_value=(Journal, None, None)),
              patch("universalddns.operator.local_operator_identity",
                    return_value="os-user"),
              patch("universalddns.operator.RecoveryDecisionJournal",
                    return_value=decision_store)):
            self.assertEqual(main(), 0)
        self.assertEqual(decision_store.record.call_args.kwargs["operator_id"], "os-user")
        self.assertEqual(decision_store.record.call_args.kwargs["expected_generation"], 3)

    def test_reconcile_statuses_do_not_retry(self):
        from dns.exception import DNSException
        from universalddns.intents import UpdateState

        class Journal:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        class Orchestrator:
            def __init__(self, outcome):
                self.outcome = outcome

            def reconcile(self, identifier, *, retry=False):
                self.assert_no_retry(retry)
                if isinstance(self.outcome, Exception):
                    raise self.outcome
                return self.outcome

            @staticmethod
            def assert_no_retry(retry):
                assert retry is False

        rrset = RecordSet("lab.invalid", "home.lab.invalid", "A", 60,
                          ("192.0.2.19",))
        from universalddns.intents import UpdateIntent
        for state, expected in ((UpdateState.FAILED, 6), (UpdateState.APPLIED, 0)):
            intent = UpdateIntent("intent-id", "principal", rrset, state)
            argv = ["operator", "--config", "test-config", "reconcile", "intent-id"]
            with (patch("sys.argv", argv),
                  patch("universalddns.operator.load_settings"),
                  patch("universalddns.operator.factories",
                        return_value=(Journal, lambda _: Orchestrator(intent), None))):
                self.assertEqual(expected, main())
        argv = ["operator", "--config", "test-config", "reconcile", "intent-id"]
        with (patch("sys.argv", argv),
              patch("universalddns.operator.load_settings"),
              patch("universalddns.operator.factories",
                    return_value=(Journal, lambda _: Orchestrator(DNSException("unavailable")), None))):
            self.assertEqual(5, main())

if __name__ == "__main__":
    unittest.main()
