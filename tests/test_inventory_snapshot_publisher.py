"""Isolated atomic snapshot publication tests."""
import sqlite3
import os
import fcntl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.inventory_snapshot import (
    publish_inventory_snapshot, snapshot_is_fresh, snapshot_fingerprint,
    read_snapshot_generation,
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
        self.assertEqual([x.name for x in self.private.iterdir()], [".inventory-publish.lock", "inventory.sqlite3"])

    def test_failure_retains_last_good_snapshot_and_cleans_staging(self):
        publish_inventory_snapshot(self.source, self.target)
        original = self.target.read_bytes()
        with patch("universalddns.inventory_snapshot.read_record_inventory",
                   side_effect=ValueError("internal details")):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_inventory_snapshot(self.source, self.target)
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(sorted(x.name for x in self.private.iterdir()), [".inventory-publish.lock", "inventory.sqlite3"])

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

    def test_directory_replacement_during_validation_refused(self):
        real_replace = os.replace

        def substitute(*args, **kwargs):
            if "src_dir_fd" in kwargs:
                replacement = self.private.parent / "private-moved"
                self.private.rename(replacement)
                self.private.mkdir(mode=0o700)
                raise OSError("injected publish failure")
            return real_replace(*args, **kwargs)

        with patch("universalddns.inventory_snapshot.os.replace",
                   side_effect=substitute):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_inventory_snapshot(self.source, self.target)
        self.assertFalse(self.target.exists())

    def test_publish_error_retains_existing_file(self):
        publish_inventory_snapshot(self.source, self.target)
        previous = self.target.read_bytes()
        with patch("universalddns.inventory_snapshot.os.replace",
                   side_effect=OSError("injected failure")):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_inventory_snapshot(self.source, self.target)
        self.assertEqual(self.target.read_bytes(), previous)

    def test_concurrent_publisher_refused(self):
        lock = self.private / ".inventory-publish.lock"
        descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_inventory_snapshot(self.source, self.target)
            self.assertFalse(self.target.exists())
        finally:
            os.close(descriptor)

    def test_expired_backup_deadline_refused_and_staging_cleaned(self):
        with patch("universalddns.inventory_snapshot.BACKUP_DEADLINE_SECONDS", -1.0):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_inventory_snapshot(self.source, self.target)
        self.assertFalse(self.target.exists())
        self.assertFalse(any(p.name.startswith(".inventory-") and
                             p.name != ".inventory-publish.lock"
                             for p in self.private.iterdir()))

    def test_insecure_lock_permissions_refused(self):
        lock = self.private / ".inventory-publish.lock"
        lock.write_bytes(b"")
        lock.chmod(0o666)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            publish_inventory_snapshot(self.source, self.target)
        self.assertFalse(self.target.exists())

    def test_hardlinked_lock_refused(self):
        lock = self.private / ".inventory-publish.lock"
        lock.write_bytes(b"")
        os.link(lock, self.private / "second-link")
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            publish_inventory_snapshot(self.source, self.target)

    def test_cleanup_uses_pinned_directory_after_rename(self):
        moved = self.private.parent / "private-renamed"

        def disrupt(*args, **kwargs):
            self.private.rename(moved)
            self.private.mkdir(mode=0o700)
            raise ValueError("injected crash")

        with patch("universalddns.inventory_snapshot.read_record_inventory",
                   side_effect=disrupt):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_inventory_snapshot(self.source, self.target)
        self.assertFalse(any(p.name.startswith(".inventory-") and
                             p.name != ".inventory-publish.lock"
                             for p in moved.iterdir()))
        self.assertEqual(list(self.private.iterdir()), [])

    def test_abandoned_staging_removed_before_publish(self):
        orphan = self.private / ".inventory-orphan.sqlite3"
        orphan.write_bytes(b"incomplete")
        orphan.chmod(0o600)
        self.assertEqual(publish_inventory_snapshot(self.source, self.target)["total_records"], 1)
        self.assertFalse(orphan.exists())
        self.assertTrue(self.target.exists())

    def test_unsafe_orphan_fails_closed_without_deletion(self):
        orphan = self.private / ".inventory-unsafe.sqlite3"
        orphan.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            publish_inventory_snapshot(self.source, self.target)
        self.assertTrue(orphan.is_symlink())
        self.assertFalse(self.target.exists())

    def test_recovery_refuses_when_lock_is_held(self):
        orphan = self.private / ".inventory-orphan.sqlite3"
        orphan.write_bytes(b"incomplete")
        orphan.chmod(0o600)
        lock = self.private / ".inventory-publish.lock"
        descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_inventory_snapshot(self.source, self.target)
            self.assertTrue(orphan.exists())
        finally:
            os.close(descriptor)

    def test_fingerprint_changes_on_tampering(self):
        publish_inventory_snapshot(self.source, self.target)
        baseline = snapshot_fingerprint(self.target)
        self.assertEqual(len(baseline), 64)
        self.assertEqual(snapshot_fingerprint(self.target), baseline)
        with self.target.open("ab") as output:
            output.write(b"tampered")
        self.assertNotEqual(snapshot_fingerprint(self.target), baseline)

    def test_prepublication_integrity_failure_keeps_last_good(self):
        publish_inventory_snapshot(self.source, self.target)
        before = snapshot_fingerprint(self.target)
        with patch("universalddns.inventory_snapshot.snapshot_fingerprint",
                   side_effect=OSError("integrity failure")):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_inventory_snapshot(self.source, self.target)
        self.assertEqual(snapshot_fingerprint(self.target), before)

    def test_generation_changes_atomically_on_replacement(self):
        publish_inventory_snapshot(self.source, self.target)
        first = read_snapshot_generation(self.target)
        self.assertEqual(len(first[0]), 32)
        publish_inventory_snapshot(self.source, self.target)
        second = read_snapshot_generation(self.target)
        self.assertNotEqual(first[0], second[0])
        self.assertGreaterEqual(second[1], first[1])

    def test_failed_publication_preserves_generation(self):
        publish_inventory_snapshot(self.source, self.target)
        original = read_snapshot_generation(self.target)
        with patch("universalddns.inventory_snapshot.os.replace",
                   side_effect=OSError("interrupted before rename")):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_inventory_snapshot(self.source, self.target)
        self.assertEqual(read_snapshot_generation(self.target), original)

    def test_missing_generation_rejected(self):
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_snapshot_generation(self.source)

    def test_freshness_is_bounded(self):
        publish_inventory_snapshot(self.source, self.target)
        now = self.target.stat().st_mtime
        self.assertTrue(snapshot_is_fresh(self.target, now=now))
        self.assertFalse(snapshot_is_fresh(self.target, now=now + 301))
        self.assertFalse(snapshot_is_fresh(self.target, now=now - 1))
        self.assertFalse(snapshot_is_fresh(self.private / "absent"))


if __name__ == "__main__":
    unittest.main()
