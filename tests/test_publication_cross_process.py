"""Linux-only isolated multiprocess publication and crash acceptance fixtures.

No live SQLite databases, service accounts, broker endpoints, or persistent sockets.
"""
import multiprocessing
import os
import shutil
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.publication_ack import publish_and_acknowledge
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry


def _publish_worker(source, target, entered=None, release=None):
    """Process-local issuance cannot authenticate publication in another PID."""
    if entered is not None:
        from universalddns import inventory_snapshot
        original = inventory_snapshot._clean_abandoned_staging

        def hold_lock(fd):
            entered.set()
            if not release.wait(10):
                raise RuntimeError("lock fixture timeout")
            return original(fd)

        with patch.object(inventory_snapshot, "_clean_abandoned_staging",
                          side_effect=hold_lock):
            _publish_worker(source, target)
        return
    try:
        publish_and_acknowledge(source, target, SnapshotIssuanceRegistry())
    except ValueError:
        raise SystemExit(2)


def _crash_worker(source, target, boundary):
    from universalddns import inventory_snapshot
    if boundary == "before-rename":
        with patch.object(inventory_snapshot.os, "replace",
                          side_effect=lambda *a, **kw: os._exit(71)):
            publish_and_acknowledge(source, target, SnapshotIssuanceRegistry())
    elif boundary == "post-rename-pre-fsync":
        actual = os.fsync

        def stop_at_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                os._exit(72)
            return actual(fd)

        with patch.object(inventory_snapshot.os, "fsync",
                          side_effect=stop_at_directory):
            publish_and_acknowledge(source, target, SnapshotIssuanceRegistry())
    elif boundary in ("post-fsync-pre-ack", "post-ack"):
        actual = SnapshotIssuanceRegistry.issue

        def stop_at_ack(self, generation, **kwargs):
            if boundary == "post-ack":
                actual(self, generation, **kwargs)
            os._exit(73 if boundary == "post-fsync-pre-ack" else 74)

        with patch.object(SnapshotIssuanceRegistry, "issue", stop_at_ack):
            publish_and_acknowledge(source, target, SnapshotIssuanceRegistry())
    else:
        raise AssertionError(boundary)
    raise AssertionError("crash injection did not fire")


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork"),
                     "requires Linux-style fork and flock")
class CrossProcessPublicationAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "source.sqlite3"
        self.private = root / "private"
        self.private.mkdir(mode=0o700)
        self.target = self.private / "inventory.sqlite3"
        self.context = multiprocessing.get_context("fork")
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))

    def _join(self, process):
        process.join(12)
        if process.is_alive():
            process.kill()
            process.join(3)
            self.fail("isolated child process exceeded deadline")

    def test_competing_process_refused_while_flock_held(self):
        entered = self.context.Event()
        release = self.context.Event()
        first = self.context.Process(
            target=_publish_worker,
            args=(str(self.source), str(self.target), entered, release))
        first.start()
        try:
            self.assertTrue(entered.wait(8), "publisher never obtained lock")
            second = self.context.Process(
                target=_publish_worker, args=(str(self.source), str(self.target)))
            second.start()
            self._join(second)
            self.assertEqual(second.exitcode, 2, "competing publisher was not refused")
        finally:
            release.set()
            self._join(first)
        self.assertEqual(first.exitcode, 0)
        snapshot = read_consistent_snapshot(self.target)
        self.assertEqual(snapshot["total_records"], 1)
        # The parent process observed no authenticated issuance.
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            SnapshotIssuanceRegistry().validate(snapshot)
        self.assertEqual(list(self.private.glob(".inventory-*.sqlite3")), [])

    def test_crash_windows_fail_closed_and_next_publication_cleans_staging(self):
        boundaries = {
            "before-rename": (71, False),
            "post-rename-pre-fsync": (72, True),
            "post-fsync-pre-ack": (73, True),
            "post-ack": (74, True),
        }
        for boundary, (exit_status, renamed) in boundaries.items():
            with self.subTest(boundary=boundary):
                with tempfile.TemporaryDirectory(dir=self.tmp.name) as work:
                    private = Path(work) / "private"
                    private.mkdir(mode=0o700)
                    target = private / "inventory.sqlite3"
                    initial = SnapshotIssuanceRegistry()
                    publish_and_acknowledge(self.source, target, initial)
                    old = read_consistent_snapshot(target)
                    # The test observer explicitly refuses to trust state from
                    # an uncoordinated publishing process.
                    initial.invalidate()
                    child = self.context.Process(
                        target=_crash_worker,
                        args=(str(self.source), str(target), boundary))
                    child.start()
                    self._join(child)
                    self.assertEqual(child.exitcode, exit_status)
                    observed = read_consistent_snapshot(target)
                    self.assertEqual(observed["generation"] != old["generation"], renamed)
                    for record in (old, observed):
                        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                            initial.validate(record)
                    # A crash may leave staging behind; recovery must clean it.
                    recovered = SnapshotIssuanceRegistry()
                    publish_and_acknowledge(self.source, target, recovered)
                    recovered.validate(read_consistent_snapshot(target))
                    self.assertEqual(list(private.glob(".inventory-*.sqlite3")), [])


if __name__ == "__main__":
    unittest.main()
