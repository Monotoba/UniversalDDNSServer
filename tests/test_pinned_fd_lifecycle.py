"""Descriptor-number substitution and interrupted verifier cleanup regression tests."""
import multiprocessing
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns import supervised_verifier
from universalddns.inventory_snapshot import publish_inventory_snapshot
from universalddns.supervised_verifier import verify_snapshot_supervised


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork"),
                     "fork-only descriptor fixture")
class DescriptorLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source.sqlite3"
        directory = root / "private"
        directory.mkdir(mode=0o700)
        self.target = directory / "snapshot.sqlite3"
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))
        publish_inventory_snapshot(self.source, self.target)

    def test_fd_number_substitution_during_worker_rejected(self):
        fd = os.open(self.target, os.O_RDONLY)
        backup = os.dup(fd)
        other = self.target.parent / "other.sqlite3"
        publish_inventory_snapshot(self.source, other)
        replacement = os.open(other, os.O_RDONLY)
        original = supervised_verifier._read_exact_until
        switched = False

        def change(fd_number, count, deadline):
            nonlocal switched
            data = original(fd_number, count, deadline)
            if count == supervised_verifier._FRAME.size and not switched:
                switched = True
                os.dup2(replacement, fd)
            return data

        try:
            with patch.object(supervised_verifier, "_read_exact_until",
                              side_effect=change):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    verify_snapshot_supervised(self.target, pinned_fd=fd)
            self.assertTrue(switched)
            self.assertEqual(verify_snapshot_supervised(
                self.target, pinned_fd=backup)["total_records"], 1)
        finally:
            os.close(replacement)
            os.close(backup)
            os.close(fd)

    def test_forced_worker_timeout_releases_parent_fds_and_recovers(self):
        fd = os.open(self.target, os.O_RDONLY)
        initial = {p.pid for p in multiprocessing.active_children()}
        baseline = (len(os.listdir("/proc/self/fd"))
                    if Path("/proc/self/fd").exists() else None)

        def hang(path, channel, pinned_fd=None):
            time.sleep(3)

        try:
            with patch.object(supervised_verifier, "_verification_child",
                              side_effect=hang):
                for _ in range(3):
                    with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                        verify_snapshot_supervised(self.target, pinned_fd=fd,
                                                   timeout_seconds=0.1)
                    self.assertEqual({p.pid for p in multiprocessing.active_children()},
                                     initial)
                    if baseline is not None:
                        self.assertLessEqual(len(os.listdir("/proc/self/fd")), baseline)
            self.assertEqual(verify_snapshot_supervised(
                self.target, pinned_fd=fd)["total_records"], 1)
        finally:
            os.close(fd)


if __name__ == "__main__":
    unittest.main()
