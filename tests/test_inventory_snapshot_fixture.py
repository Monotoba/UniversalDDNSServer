"""Isolated proof that SQLite backup snapshots include committed WAL data."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from universalddns.record_inventory import read_record_inventory


class InventorySnapshotFixtureTests(unittest.TestCase):
    def test_backup_of_live_wal_is_consistent_and_readable_without_sidecars(self):
        with tempfile.TemporaryDirectory() as directory:
            live = Path(directory) / "live.sqlite3"
            snap = Path(directory) / "snapshot.sqlite3"
            writer = sqlite3.connect(live)
            try:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute("""CREATE TABLE managed_records (
                    record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                    record_type TEXT, ttl INTEGER, values_json TEXT,
                    revision INTEGER, active INTEGER)""")
                writer.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                               ("committed", "example.test", "a", "A", 300, "[]", 1, 1))
                writer.commit()
                writer.execute("BEGIN IMMEDIATE")
                writer.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                               ("uncommitted", "example.test", "b", "A", 300, "[]", 1, 0))
                # A separate reader sees a committed snapshot, not the writer's transaction.
                with sqlite3.connect(f"file:{live}?mode=ro", uri=True) as reader:
                    with sqlite3.connect(snap) as destination:
                        reader.backup(destination)
                        mode = destination.execute("PRAGMA journal_mode=DELETE").fetchone()
                        self.assertEqual(mode, ("delete",))
                self.assertEqual(snap.read_bytes()[18:20], bytes((1, 1)))
                self.assertFalse(Path(str(snap) + "-wal").exists())
                self.assertFalse(Path(str(snap) + "-shm").exists())
                before = snap.read_bytes()
                self.assertEqual(read_record_inventory(snap), {
                    "total_records": 1,
                    "staged_active_records": 1,
                    "staged_inactive_records": 0,
                })
                self.assertEqual(snap.read_bytes(), before)
            finally:
                writer.rollback()
                writer.close()


if __name__ == "__main__":
    unittest.main()
