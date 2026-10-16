"""Fixture-based tests: isolated inventory must never initialize SQLite."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.record_inventory import read_record_inventory


class RecordInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite3"

    def initialize(self, rows=()):
        with sqlite3.connect(self.path) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT NOT NULL,
                name TEXT NOT NULL, record_type TEXT NOT NULL,
                ttl INTEGER NOT NULL, values_json TEXT NOT NULL,
                revision INTEGER NOT NULL, active INTEGER NOT NULL)""")
            db.executemany(
                "INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                [(str(i), "example.test", str(i), "A", 300,
                  '["127.0.0.1"]', 1, state)
                 for i, state in enumerate(rows)],
            )

    def test_missing_database_is_not_created(self):
        with self.assertRaisesRegex(ValueError, "inventory unavailable"):
            read_record_inventory(self.path)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_empty_and_mixed_counts_no_disk_modification(self):
        self.initialize()
        initial = self.path.read_bytes()
        self.assertEqual(read_record_inventory(self.path), {
            "total_records": 0, "staged_active_records": 0,
            "staged_inactive_records": 0,
        })
        self.assertEqual(self.path.read_bytes(), initial)
        with sqlite3.connect(self.path) as db:
            db.executemany("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                           [(str(i), "example.test", str(i), "A", 300, "[]", 1, i % 2)
                            for i in range(7)])
        previous = self.path.read_bytes()
        self.assertEqual(read_record_inventory(self.path), {
            "total_records": 7, "staged_active_records": 3,
            "staged_inactive_records": 4,
        })
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], [self.path.name])

    def test_missing_table_and_invalid_schema_fail_closed(self):
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE something_else (id TEXT)")
        with self.assertRaisesRegex(ValueError, "inventory unavailable"):
            read_record_inventory(self.path)

    def test_invalid_active_flag_fails_closed(self):
        self.initialize([2])
        with self.assertRaisesRegex(ValueError, "inventory unavailable"):
            read_record_inventory(self.path)

    def test_wal_snapshot_read_does_not_mutate_existing_files(self):
        self.initialize([0, 1])
        writer = sqlite3.connect(self.path)
        try:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                           ("third", "example.test", "third", "A", 300, "[]", 1, 1))
            writer.commit()
            before = {p.name: p.read_bytes() for p in self.path.parent.iterdir()}
            self.assertEqual(read_record_inventory(self.path)["total_records"], 3)
            after = {p.name: p.read_bytes() for p in self.path.parent.iterdir()}
            self.assertEqual(after, before)
        finally:
            writer.close()

    def test_writer_reserved_lock_does_not_block_snapshot(self):
        self.initialize([0])
        writer = sqlite3.connect(self.path, timeout=0.2)
        try:
            writer.execute("BEGIN IMMEDIATE")
            writer.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                           ("pending", "example.test", "pending", "A", 300, "[]", 1, 1))
            self.assertEqual(read_record_inventory(self.path)["total_records"], 1)
        finally:
            writer.rollback()
            writer.close()

    def test_query_deadline_interrupts_large_scan(self):
        self.initialize([0])
        with patch("universalddns.record_inventory.QUERY_DEADLINE_SECONDS", -1.0):
            with self.assertRaisesRegex(ValueError, "^inventory unavailable$"):
                read_record_inventory(self.path)

    def test_unexpected_sqlite_error_is_generic(self):
        self.initialize([0])
        with patch("universalddns.record_inventory.sqlite3.connect",
                   side_effect=sqlite3.DatabaseError("secret database path")):
            with self.assertRaisesRegex(ValueError, "^inventory unavailable$"):
                read_record_inventory(self.path)


if __name__ == "__main__":
    unittest.main()
