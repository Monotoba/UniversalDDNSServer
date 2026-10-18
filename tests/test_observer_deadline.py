"""Isolated deadline checkpoint acceptance tests, not a hard-timeout guarantee."""
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns import authorized_observer
from universalddns.authorized_observer import publish_with_authorized_child
from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry


class ObserverDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
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

    def test_late_initial_snapshot_read_does_not_issue(self):
        publish_with_authorized_child(self.source, self.target, self.registry)
        previous = read_consistent_snapshot(self.target)
        original = authorized_observer.read_consistent_snapshot

        def delayed(path):
            result = original(path)
            time.sleep(0.1)
            return result

        with patch.object(authorized_observer, "read_consistent_snapshot",
                          side_effect=delayed):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_with_authorized_child(
                    self.source, self.target, self.registry, timeout_seconds=0.05)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate(previous)

    def test_late_final_verification_revokes_issuance(self):
        original = authorized_observer.read_current_authorized_snapshot

        def delayed(path, registry):
            result = original(path, registry)
            time.sleep(0.1)
            return result

        with patch.object(authorized_observer, "read_current_authorized_snapshot",
                          side_effect=delayed):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_with_authorized_child(
                    self.source, self.target, self.registry, timeout_seconds=0.05)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate(read_consistent_snapshot(self.target))
        self.assertEqual(publish_with_authorized_child(
            self.source, self.target, self.registry)["total_records"], 1)

    def test_success_with_sufficient_deadline(self):
        result = publish_with_authorized_child(
            self.source, self.target, self.registry, timeout_seconds=10)
        self.assertEqual(result["total_records"], 1)
        self.registry.validate(read_consistent_snapshot(self.target))


if __name__ == "__main__":
    unittest.main()
