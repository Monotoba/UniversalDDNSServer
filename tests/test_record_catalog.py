import tempfile
import unittest
from pathlib import Path

from universalddns.domain import RecordSet
from universalddns.record_catalog import RecordCatalog


class RecordCatalogTests(unittest.TestCase):
    def test_create_list_update_restart_and_revision_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            initial = RecordSet("example.org", "a.example.org", "A", 60, ("192.0.2.1",))
            updated = RecordSet("example.org", "a.example.org", "A", 120, ("192.0.2.2",))
            with RecordCatalog(path) as first, RecordCatalog(path) as other:
                self.assertEqual(first.create("home", initial), 1)
                self.assertEqual(first.get("home"), (initial, 1))
                self.assertEqual(first.list_records(), (("home", initial, 1),))
                self.assertEqual(other.update("home", updated, expected_revision=1), 2)
                with self.assertRaisesRegex(ValueError, "stale revision"):
                    first.update("home", initial, expected_revision=1)
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    first.create("other", updated)
            with RecordCatalog(path) as reopened:
                self.assertEqual(reopened.get("home"), (updated, 2))
                self.assertIsNone(reopened.get("missing"))

    def test_rejects_invalid_ids_and_duplicate_rrsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            with RecordCatalog(Path(tmp) / "state.db") as catalog:
                record = RecordSet("example.org", "a.example.org", "A", 60,
                                   ("192.0.2.1",))
                for identifier in ("", "with space", "x" * 129, "../bad"):
                    with self.subTest(identifier=identifier):
                        with self.assertRaises(ValueError):
                            catalog.create(identifier, record)
                catalog.create("first", record)
                with self.assertRaises(ValueError):
                    catalog.create("first", record)
                with self.assertRaises(ValueError):
                    catalog.create("second", record)
                with self.assertRaises(ValueError):
                    catalog.update("first", record, expected_revision=0)
                with self.assertRaises(ValueError):
                    catalog.list_records(limit=0)
