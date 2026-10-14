"""Local operator inspection behavior is bounded and read-only."""
import tempfile
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


if __name__ == "__main__":
    unittest.main()
