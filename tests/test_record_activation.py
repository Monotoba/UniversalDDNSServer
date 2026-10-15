"""Activation staging must preserve legacy records and reject stale edits."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from universalddns.domain import RecordSet
from universalddns.record_catalog import RecordCatalog


class ActivationTests(unittest.TestCase):
    def test_activation_revision_and_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.db"
            record = RecordSet("example.org", "a.example.org", "A", 60,
                               ("192.0.2.11",))
            with RecordCatalog(path) as first, RecordCatalog(path) as second:
                first.create("a", record)
                self.assertEqual(first.active_records(), ())
                self.assertEqual(first.set_active("a", expected_revision=1, active=True), 2)
                self.assertEqual(second.active_records(), (("a", record, 2),))
                with self.assertRaises(ValueError):
                    second.set_active("a", expected_revision=1, active=False)
                self.assertEqual(second.set_active("a", expected_revision=2, active=False), 3)
                self.assertEqual(first.active_records(), ())
            with RecordCatalog(path) as reopened:
                self.assertEqual(reopened.get("a"), (record, 3))
                with self.assertRaises(ValueError):
                    reopened.set_active("a", expected_revision=3, active=1)

    def test_legacy_catalog_migration_is_inactive(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "legacy.db"
            with sqlite3.connect(path) as db:
                db.execute("""CREATE TABLE managed_records (
                    record_id TEXT PRIMARY KEY, zone TEXT NOT NULL,
                    name TEXT NOT NULL, record_type TEXT NOT NULL,
                    ttl INTEGER NOT NULL, values_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    UNIQUE (zone,name,record_type)
                )""")
                db.execute("""INSERT INTO managed_records
                    (record_id,zone,name,record_type,ttl,values_json)
                    VALUES ('old','example.org.','old.example.org.','A',60,'["192.0.2.20"]')""")
            with RecordCatalog(path) as catalog:
                self.assertEqual(catalog.active_records(), ())
                self.assertEqual(catalog.get("old")[1], 1)
                self.assertEqual(catalog.set_active("old", expected_revision=1, active=True), 2)
