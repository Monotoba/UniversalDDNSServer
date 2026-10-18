"""Cooperative full-chain fencing and noncooperative writer negative acceptance."""
import multiprocessing
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from universalddns.inventory_snapshot import publish_inventory_snapshot
from universalddns.observer_session import (
    observer_session, publish_in_observer_session,
)
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry


def _hold_session(path, ready, release):
    with observer_session(path):
        ready.set()
        release.wait(5)


def _direct_publish(source, target, output):
    try:
        publish_inventory_snapshot(source, target)
        output.put("published")
    except ValueError:
        output.put("rejected")


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork"),
                     "requires Linux fork")
class FencedHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "source.sqlite3"
        directory = root / "private"
        directory.mkdir(mode=0o700)
        self.destination = directory / "snapshot.sqlite3"
        self.registry = SnapshotIssuanceRegistry()
        self.ctx = multiprocessing.get_context("fork")
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))

    def test_full_chain_succeeds_under_cooperative_session(self):
        result = publish_in_observer_session(
            self.source, self.destination, self.registry,
            descriptor_handoff=True)
        self.assertEqual(result["total_records"], 1)
        self.registry.validate(result)

    def test_contending_cooperative_session_refused_and_recovers(self):
        ready, release = self.ctx.Event(), self.ctx.Event()
        child = self.ctx.Process(
            target=_hold_session, args=(self.destination, ready, release))
        child.start()
        try:
            self.assertTrue(ready.wait(5))
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_in_observer_session(
                    self.source, self.destination, self.registry,
                    descriptor_handoff=True)
        finally:
            release.set()
            child.join(5)
            if child.is_alive():
                child.kill()
                child.join()
        self.assertEqual(child.exitcode, 0)
        result = publish_in_observer_session(
            self.source, self.destination, self.registry,
            descriptor_handoff=True)
        self.registry.validate(result)

    def test_crashed_holder_releases_fence_for_full_chain(self):
        import signal
        ready, release = self.ctx.Event(), self.ctx.Event()
        child = self.ctx.Process(
            target=_hold_session, args=(self.destination, ready, release))
        child.start()
        try:
            self.assertTrue(ready.wait(5))
        finally:
            if child.is_alive():
                child.kill()
            child.join(5)
        self.assertEqual(child.exitcode, -signal.SIGKILL)
        result = publish_in_observer_session(
            self.source, self.destination, self.registry,
            descriptor_handoff=True)
        self.registry.validate(result)

    def test_direct_writer_still_bypasses_cooperative_fence(self):
        ready, release = self.ctx.Event(), self.ctx.Event()
        output = self.ctx.Queue()
        holder = self.ctx.Process(
            target=_hold_session, args=(self.destination, ready, release))
        holder.start()
        writer = None
        try:
            self.assertTrue(ready.wait(5))
            writer = self.ctx.Process(target=_direct_publish, args=(
                self.source, self.destination, output))
            writer.start()
            writer.join(5)
            self.assertFalse(writer.is_alive())
            self.assertEqual(output.get(timeout=2), "published")
        finally:
            release.set()
            if writer is not None and writer.is_alive():
                writer.kill()
                writer.join()
            holder.join(5)
            if holder.is_alive():
                holder.kill()
                holder.join()
            output.close()
            output.join_thread()
        # This deliberate negative test proves that the observer lock is not
        # mandatory writer authorization or isolation from same-UID writers.


if __name__ == "__main__":
    unittest.main()
