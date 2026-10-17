"""Generation-consistent snapshot reader under atomic replacement."""
import sqlite3
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.inventory_snapshot import publish_inventory_snapshot


class ConsistentSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.live = root / "live.sqlite3"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.snapshot = private / "inventory.sqlite3"
        with sqlite3.connect(self.live) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("first", "test", "a", "A", 300, "[]", 1, 1))

    def test_explicit_trusted_producer_identity(self):
        publish_inventory_snapshot(self.live, self.snapshot)
        owner = self.snapshot.stat().st_uid
        self.assertEqual(read_consistent_snapshot(
            self.snapshot, trusted_producer_uid=owner)["total_records"], 1)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_consistent_snapshot(self.snapshot, trusted_producer_uid=owner + 1)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_consistent_snapshot(self.snapshot, trusted_producer_uid=True)

    def test_generation_matches_counts(self):
        publish_inventory_snapshot(self.live, self.snapshot)
        result = read_consistent_snapshot(self.snapshot)
        self.assertEqual(result["total_records"], 1)
        self.assertEqual(result["staged_active_records"], 1)
        self.assertEqual(len(result["generation"]), 32)

    def test_atomic_replace_during_read_returns_old_generation(self):
        publish_inventory_snapshot(self.live, self.snapshot)
        original = read_consistent_snapshot(self.snapshot)
        with sqlite3.connect(self.live) as db:
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("second", "test", "b", "A", 300, "[]", 1, 0))
        connect = sqlite3.connect
        replaced = [False]

        def swap_before_connect(*args, **kwargs):
            if not replaced[0]:
                replaced[0] = True
                publish_inventory_snapshot(self.live, self.snapshot)
            return connect(*args, **kwargs)

        with patch("universalddns.consistent_snapshot.sqlite3.connect",
                   side_effect=swap_before_connect):
            pinned = read_consistent_snapshot(self.snapshot)
        self.assertTrue(replaced[0])
        self.assertEqual(pinned["generation"], original["generation"])
        self.assertEqual(pinned["total_records"], 1)
        current = read_consistent_snapshot(self.snapshot)
        self.assertNotEqual(current["generation"], original["generation"])
        self.assertEqual(current["total_records"], 2)

    def test_world_readable_snapshot_refused(self):
        publish_inventory_snapshot(self.live, self.snapshot)
        self.snapshot.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_consistent_snapshot(self.snapshot)

    def test_hardlinked_snapshot_refused(self):
        publish_inventory_snapshot(self.live, self.snapshot)
        os.link(self.snapshot, self.snapshot.parent / "alias.sqlite3")
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_consistent_snapshot(self.snapshot)

    def test_corrupted_header_refused(self):
        publish_inventory_snapshot(self.live, self.snapshot)
        with self.snapshot.open("r+b") as stream:
            stream.write(b"not-sqlite")
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_consistent_snapshot(self.snapshot)

    def test_changed_file_during_read_refused(self):
        publish_inventory_snapshot(self.live, self.snapshot)
        original_read = os.read
        changed = [False]

        def modify_after_first_chunk(fd, count):
            chunk = original_read(fd, count)
            if not changed[0]:
                changed[0] = True
                with self.snapshot.open("ab") as stream:
                    stream.write(b"changed")
            return chunk

        with patch("universalddns.consistent_snapshot.os.read",
                   side_effect=modify_after_first_chunk):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                read_consistent_snapshot(self.snapshot)

    def test_invalid_active_values_fail_closed(self):
        publish_inventory_snapshot(self.live, self.snapshot)
        with sqlite3.connect(self.snapshot) as db:
            db.execute("UPDATE managed_records SET active=7")
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_consistent_snapshot(self.snapshot)

    def test_duplicate_generation_rows_fail_closed(self):
        publish_inventory_snapshot(self.live, self.snapshot)
        with sqlite3.connect(self.snapshot) as db:
            db.execute("INSERT INTO inventory_generation "
                       "SELECT generation, created_at FROM inventory_generation")
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_consistent_snapshot(self.snapshot)

    def test_wal_mode_snapshot_rejected(self):
        publish_inventory_snapshot(self.live, self.snapshot)
        with sqlite3.connect(self.snapshot) as db:
            self.assertEqual(db.execute("PRAGMA journal_mode=WAL").fetchone(), ("wal",))
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_consistent_snapshot(self.snapshot)

    def test_oversized_snapshot_rejected_before_deserialization(self):
        publish_inventory_snapshot(self.live, self.snapshot)
        with patch("universalddns.consistent_snapshot.MAX_SNAPSHOT_BYTES", 100):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                read_consistent_snapshot(self.snapshot)

    def test_missing_or_symlink_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_consistent_snapshot(self.snapshot)
        self.snapshot.symlink_to(self.live)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_consistent_snapshot(self.snapshot)

    def test_rollback_database_without_metadata_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_consistent_snapshot(self.live)


if __name__ == "__main__":
    unittest.main()
