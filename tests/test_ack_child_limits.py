"""Linux-only resource-limit and SIGKILL recovery acceptance for isolated observer."""
import multiprocessing
import os
import resource
import signal
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.ack_frame import FRAME_BYTES
from universalddns.authorized_observer import publish_with_authorized_child
from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.observer_session import observer_session
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry


def _capped_stall(source, destination, connection, nonce):
    """Apply caps strictly in child; partial message must never be issued."""
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    connection.send_bytes(b"x" * FRAME_BYTES)
    time.sleep(5)


def _killed_holding_lock(target, ready):
    with observer_session(target):
        ready.set()
        signal.pause()


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork")
                     and Path("/proc/self/fd").is_dir(),
                     "requires Linux fork, resource and procfs")
class ObserverLimitAndKillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "live.sqlite3"
        directory = root / "private"
        directory.mkdir(mode=0o700)
        self.target = directory / "snapshot.sqlite3"
        self.registry = SnapshotIssuanceRegistry()
        self.ctx = multiprocessing.get_context("fork")
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))

    def test_child_resource_limits_are_scoped_and_failure_recovers(self):
        from universalddns import authorized_observer
        limits = tuple(resource.getrlimit(kind) for kind in
                       (resource.RLIMIT_NOFILE, resource.RLIMIT_AS,
                        resource.RLIMIT_CPU))
        old_children = {p.pid for p in multiprocessing.active_children()}
        baseline = len(os.listdir("/proc/self/fd"))
        with patch.object(authorized_observer, "_publisher_child",
                          side_effect=_capped_stall):
            for _ in range(3):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    publish_with_authorized_child(
                        self.source, self.target, self.registry,
                        timeout_seconds=0.15)
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    self.registry.validate({"generation": "a" * 32})
        self.assertEqual(limits, tuple(resource.getrlimit(kind) for kind in
                         (resource.RLIMIT_NOFILE, resource.RLIMIT_AS,
                          resource.RLIMIT_CPU)))
        self.assertEqual(old_children, {p.pid for p in multiprocessing.active_children()})
        self.assertLessEqual(len(os.listdir("/proc/self/fd")), baseline)
        result = publish_with_authorized_child(
            self.source, self.target, self.registry)
        self.assertEqual(result["total_records"], 1)

    def test_sigkill_releases_observer_lock_and_requires_fresh_issuance(self):
        ready = self.ctx.Event()
        child = self.ctx.Process(
            target=_killed_holding_lock, args=(str(self.target), ready))
        child.start()
        try:
            self.assertTrue(ready.wait(6))
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                with observer_session(self.target):
                    pass
        finally:
            if child.is_alive():
                child.kill()
            child.join(5)
        self.assertFalse(child.is_alive())
        self.assertEqual(child.exitcode, -signal.SIGKILL)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate({"generation": "a" * 32})
        # An abandoned session doesn't create trust; a fresh publication does.
        result = publish_with_authorized_child(
            self.source, self.target, self.registry)
        self.registry.validate(read_consistent_snapshot(self.target))
        self.assertEqual(result["total_records"], 1)


if __name__ == "__main__":
    unittest.main()
