"""Publication acknowledgement and uncertainty failure ordering tests."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.publication_ack import publish_and_acknowledge
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry


class PublicationAcknowledgementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "live.db"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.target = private / "inventory.sqlite3"
        self.registry = SnapshotIssuanceRegistry()
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))

    def test_success_issues_exact_committed_generation(self):
        publish_and_acknowledge(self.source, self.target, self.registry)
        self.assertEqual(self.registry.validate(read_consistent_snapshot(self.target))
                         ["total_records"], 1)

    def test_failure_before_replace_does_not_issue(self):
        from universalddns import inventory_snapshot
        with patch.object(inventory_snapshot.os, "replace", side_effect=OSError("fail")):
            with self.assertRaises(ValueError):
                publish_and_acknowledge(self.source, self.target, self.registry)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate({"generation": "a" * 32})

    def test_post_replace_fsync_failure_invalidates_previous_issuance(self):
        publish_and_acknowledge(self.source, self.target, self.registry)
        old = read_consistent_snapshot(self.target)
        from universalddns import inventory_snapshot
        actual_fsync = os.fsync

        def reject_directory(fd):
            if os.fstat(fd).st_mode & 0o170000 == 0o040000:
                raise OSError("directory sync interrupted")
            return actual_fsync(fd)

        with patch.object(inventory_snapshot.os, "fsync", side_effect=reject_directory):
            with self.assertRaises(ValueError):
                publish_and_acknowledge(self.source, self.target, self.registry)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate(old)

    def test_callback_failure_does_not_leave_trusted_state(self):
        publish_and_acknowledge(self.source, self.target, self.registry)
        old = read_consistent_snapshot(self.target)
        with patch.object(self.registry, "issue", side_effect=ValueError("rejected")):
            with self.assertRaises(ValueError):
                publish_and_acknowledge(self.source, self.target, self.registry)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate(old)


if __name__ == "__main__":
    unittest.main()
