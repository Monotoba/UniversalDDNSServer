"""Pinned descriptor identity acceptance for isolated supervised verification."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns import authorized_observer
from universalddns.inventory_snapshot import publish_inventory_snapshot
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry
from universalddns.supervised_verifier import verify_snapshot_supervised


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork"),
                     "requires fork and inherited file descriptors")
class PinnedVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source.sqlite3"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.path = private / "snapshot.sqlite3"
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))
        publish_inventory_snapshot(self.source, self.path)

    def test_pinned_reader_observes_original_even_after_rename(self):
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            first = verify_snapshot_supervised(self.path, pinned_fd=fd)
            publish_inventory_snapshot(self.source, self.path)
            original = verify_snapshot_supervised(self.path, pinned_fd=fd)
            current = verify_snapshot_supervised(self.path)
            self.assertEqual(first["generation"], original["generation"])
            self.assertNotEqual(original["generation"], current["generation"])
        finally:
            os.close(fd)

    def test_invalid_and_writable_descriptors_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            verify_snapshot_supervised(self.path, pinned_fd=-1)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            verify_snapshot_supervised(self.path, pinned_fd=99999999)
        fd = os.open(self.path, os.O_RDWR)
        try:
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                verify_snapshot_supervised(self.path, pinned_fd=fd)
        finally:
            os.close(fd)

    def test_observer_rejects_replacement_during_pinned_verification(self):
        registry = SnapshotIssuanceRegistry()
        original = authorized_observer._read_supervised_current
        def displaced(path, deadline):
            from universalddns import supervised_verifier
            actual = supervised_verifier.verify_snapshot_supervised
            def replacement(target, *, timeout_seconds, pinned_fd=None):
                publish_inventory_snapshot(self.source, self.path)
                return actual(target, timeout_seconds=timeout_seconds,
                              pinned_fd=pinned_fd)
            with patch.object(supervised_verifier, "verify_snapshot_supervised",
                              side_effect=replacement):
                return original(path, deadline)

        with patch.object(authorized_observer, "_read_supervised_current",
                          side_effect=displaced):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                authorized_observer.publish_with_authorized_child(
                    self.source, self.path, registry, supervised_verification=True)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            registry.validate({"generation": "a" * 32})


if __name__ == "__main__":
    unittest.main()
