"""Cross-process cooperative observer-lock contention and recovery tests."""
import multiprocessing
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from universalddns.observer_session import (
    observer_session, publish_in_observer_session, read_in_observer_session,
)
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry


def _hold_session(destination, ready, release):
    with observer_session(destination):
        ready.set()
        if not release.wait(8):
            raise RuntimeError("fixture timeout")


def _crash_in_session(destination, ready):
    with observer_session(destination):
        ready.set()
        os._exit(65)


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork"),
                     "requires Linux fork and flock")
class ObserverSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "live.db"
        directory = root / "private"
        directory.mkdir(mode=0o700)
        self.target = directory / "inventory.sqlite3"
        self.registry = SnapshotIssuanceRegistry()
        self.context = multiprocessing.get_context("fork")
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))

    def _join(self, proc):
        proc.join(12)
        if proc.is_alive():
            proc.kill()
            proc.join(3)
            self.fail("fixture process hung")

    def test_contending_reader_and_publisher_refused(self):
        publish_in_observer_session(self.source, self.target, self.registry)
        ready = self.context.Event()
        release = self.context.Event()
        proc = self.context.Process(
            target=_hold_session, args=(str(self.target), ready, release))
        proc.start()
        try:
            self.assertTrue(ready.wait(6))
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                read_in_observer_session(self.target, self.registry)
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_in_observer_session(self.source, self.target, self.registry)
        finally:
            release.set()
            self._join(proc)
        self.assertEqual(proc.exitcode, 0)
        # Failed lock admission does not invalidate an existing issuance.
        self.assertEqual(
            read_in_observer_session(self.target, self.registry)["total_records"], 1)

    def test_lock_released_after_process_death(self):
        ready = self.context.Event()
        proc = self.context.Process(
            target=_crash_in_session, args=(str(self.target), ready))
        proc.start()
        self.assertTrue(ready.wait(6))
        self._join(proc)
        self.assertEqual(proc.exitcode, 65)
        result = publish_in_observer_session(
            self.source, self.target, self.registry)
        self.assertEqual(result["total_records"], 1)
        self.assertEqual(
            read_in_observer_session(self.target, self.registry)["generation"],
            result["generation"])

    def test_lock_inode_persists_across_sessions(self):
        with observer_session(self.target):
            inode = (self.target.parent / ".inventory-observer.lock").stat().st_ino
        with observer_session(self.target):
            self.assertEqual(
                (self.target.parent / ".inventory-observer.lock").stat().st_ino,
                inode)

    def test_symlink_lock_rejected(self):
        lock = self.target.parent / ".inventory-observer.lock"
        lock.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            with observer_session(self.target):
                self.fail("symlink lock was admitted")


if __name__ == "__main__":
    unittest.main()
