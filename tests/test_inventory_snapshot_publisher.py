"""Isolated atomic snapshot publication tests."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.inventory_snapshot import (
    publish_inventory_snapshot, snapshot_is_fresh,
)


class InventorySnapshotPublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source.sqlite3"
        self.private = root / "private"
        self.private.mkdir(mode=0o700)
        self.target = self.private / "inventory.sqlite3"
        with sqlite3.connect(self.source) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "example.test", "a", "A", 300, "[]", 1, 1))

    def test_atomic_publication_and_replacement(self):
        counts = publish_inventory_snapshot(self.source, self.target)
        self.assertEqual(counts["total_records"], 1)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        self.assertTrue(snapshot_is_fresh(self.target))
        old_bytes = self.target.read_bytes()
        with sqlite3.connect(self.source) as db:
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("two", "example.test", "b", "A", 300, "[]", 1, 0))
        self.assertEqual(publish_inventory_snapshot(self.source, self.target)["total_records"], 2)
        self.assertNotEqual(old_bytes, self.target.read_bytes())
        self.assertEqual([x.name for x in self.private.iterdir()], ["inventory.sqlite3"])

    def test_failure_retains_last_good_snapshot_and_cleans_staging(self):
        publish_inventory_snapshot(self.source, self.target)
        original = self.target.read_bytes()
        with patch("universalddns.inventory_snapshot.read_record_inventory",
                   side_effect=ValueError("internal details")):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_inventory_snapshot(self.source, self.target)
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual([x.name for x in self.private.iterdir()], ["inventory.sqlite3"])

    def test_missing_database_and_unsafe_destination_refused(self):
        with self.assertRaisesRegex(ValueError, "snapshot unavailable"):
            publish_inventory_snapshot(self.source.parent / "missing.sqlite3", self.target)
        self.assertFalse(self.target.exists())
        public = self.source.parent / "public"
        public.mkdir(mode=0o755)
        with self.assertRaisesRegex(ValueError, "snapshot unavailable"):
            publish_inventory_snapshot(self.source, public / "inventory.sqlite3")

    def test_symlink_destination_refused(self):
        self.target.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "snapshot unavailable"):
            publish_inventory_snapshot(self.source, self.target)

    def test_freshness_is_bounded(self):
        publish_inventory_snapshot(self.source, self.target)
        now = self.target.stat().st_mtime
        self.assertTrue(snapshot_is_fresh(self.target, now=now))
        self.assertFalse(snapshot_is_fresh(self.target, now=now + 301))
        self.assertFalse(snapshot_is_fresh(self.target, now=now - 1))
        self.assertFalse(snapshot_is_fresh(self.private / "absent"))


if __name__ == "__main__":
    unittest.main()
