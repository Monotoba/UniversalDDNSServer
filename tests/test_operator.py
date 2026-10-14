"""Local operator inspection behavior is bounded and read-only."""
import tempfile
from unittest.mock import patch

from universalddns.intents import UpdateConflict, UnknownIntent
from universalddns.operator import main
import unittest
from pathlib import Path

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.operator import describe


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


if __name__ == "__main__":
    unittest.main()
