"""Linux isolated verifier process timeout, failure and recovery acceptance."""
import multiprocessing
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.inventory_snapshot import publish_inventory_snapshot
from universalddns.supervised_verifier import verify_snapshot_supervised


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork"),
                     "requires POSIX fork")
class SupervisedVerifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "source.sqlite3"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.target = private / "snapshot.sqlite3"
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))
        publish_inventory_snapshot(self.source, self.target)

    def test_success_and_invalid_path(self):
        self.assertEqual(
            verify_snapshot_supervised(self.target)["total_records"], 1)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            verify_snapshot_supervised(self.target.with_name("missing.sqlite3"))

    def test_hung_worker_killed_reaped_and_recovery_succeeds(self):
        from universalddns import supervised_verifier
        initial = {p.pid for p in multiprocessing.active_children()}

        def stalled(path, conn):
            conn.send_bytes(b"x")
            time.sleep(3)

        with patch.object(supervised_verifier, "_verification_child",
                          side_effect=stalled):
            for _ in range(3):
                begin = time.monotonic()
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    verify_snapshot_supervised(self.target, timeout_seconds=0.1)
                self.assertLess(time.monotonic() - begin, 1.5)
                self.assertEqual(
                    initial, {p.pid for p in multiprocessing.active_children()})
        self.assertEqual(
            verify_snapshot_supervised(self.target)["total_records"], 1)

    def test_abnormal_exit_and_duplicate_metadata_fail(self):
        from universalddns import supervised_verifier
        from universalddns.supervised_verifier import _FRAME, _MAGIC

        def crash(path, conn):
            os._exit(72)

        def duplicate(path, conn):
            frame = _FRAME.pack(_MAGIC, b"a" * 16, 1, 1, 1, 0)
            conn.send_bytes(frame)
            conn.send_bytes(frame)
            conn.close()

        for worker in (crash, duplicate):
            with patch.object(supervised_verifier, "_verification_child",
                              side_effect=worker):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    verify_snapshot_supervised(self.target)

    def test_rejects_invalid_timeout(self):
        for value in (0, -1, 31, "bad", True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    verify_snapshot_supervised(self.target, timeout_seconds=value)


if __name__ == "__main__":
    unittest.main()
