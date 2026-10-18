"""Repeated process and descriptor cleanup in the isolated acknowledgement path."""
import multiprocessing
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.ack_frame import FRAME_BYTES
from universalddns.authorized_observer import publish_with_authorized_child
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry


def _stalled_child(source, destination, connection, nonce):
    os.write(connection.fileno(), FRAME_BYTES.to_bytes(4, "big") + b"x")
    time.sleep(5)


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork")
                     and Path("/proc/self/fd").is_dir(),
                     "Linux procfs and fork required for FD assertions")
class ObserverLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "live.sqlite3"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.target = private / "snapshot.sqlite3"
        self.registry = SnapshotIssuanceRegistry()
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))

    def _fd_count(self):
        return len(os.listdir("/proc/self/fd"))

    def test_repeated_timeouts_leave_no_children_fds_or_issuance(self):
        from universalddns import authorized_observer
        original_children = {p.pid for p in multiprocessing.active_children()}
        baseline = self._fd_count()
        with patch.object(authorized_observer, "_publisher_child",
                          side_effect=_stalled_child):
            for _ in range(6):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    publish_with_authorized_child(
                        self.source, self.target, self.registry,
                        timeout_seconds=0.05)
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    self.registry.validate({"generation": "a" * 32})
                self.assertLessEqual(self._fd_count(), baseline)
                self.assertEqual(
                    {p.pid for p in multiprocessing.active_children()},
                    original_children)
        recovered = publish_with_authorized_child(
            self.source, self.target, self.registry)
        self.assertEqual(recovered["total_records"], 1)
        self.assertLessEqual(self._fd_count(), baseline)

    def test_parent_interruption_revokes_issued_state_and_reaps_child(self):
        from universalddns import authorized_observer
        publish_with_authorized_child(self.source, self.target, self.registry)
        baseline = self._fd_count()
        children = {p.pid for p in multiprocessing.active_children()}
        with patch.object(authorized_observer, "_read_bounded_ack",
                          side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                publish_with_authorized_child(
                    self.source, self.target, self.registry,
                    timeout_seconds=0.2)
        self.assertLessEqual(self._fd_count(), baseline)
        self.assertEqual(
            {p.pid for p in multiprocessing.active_children()}, children)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate({"generation": "a" * 32})
        publish_with_authorized_child(self.source, self.target, self.registry)
        self.assertLessEqual(self._fd_count(), baseline)


if __name__ == "__main__":
    unittest.main()
