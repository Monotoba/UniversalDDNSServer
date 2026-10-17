"""Opt-in supervised observer trust, mismatch, timeout and race acceptance."""
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.authorized_observer import publish_with_authorized_child
from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.inventory_snapshot import publish_inventory_snapshot
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork"),
                     "requires fork-based isolated verifier")
class SupervisedObserverAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "live.sqlite3"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.destination = private / "inventory.sqlite3"
        self.registry = SnapshotIssuanceRegistry()
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))

    def _publish(self, timeout=10):
        return publish_with_authorized_child(
            self.source, self.destination, self.registry,
            timeout_seconds=timeout, supervised_verification=True)

    def test_success_uses_supervised_verification_and_parent_issuance(self):
        result = self._publish()
        self.assertEqual(result["total_records"], 1)
        self.registry.validate(read_consistent_snapshot(self.destination))
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            SnapshotIssuanceRegistry().validate(result)

    def test_mismatched_generation_refused_without_issuance(self):
        from universalddns import supervised_verifier
        original = supervised_verifier.verify_snapshot_supervised

        def mismatch(path, *, timeout_seconds):
            record = original(path, timeout_seconds=timeout_seconds)
            return {**record, "generation": "a" * 32}

        with patch.object(supervised_verifier, "verify_snapshot_supervised",
                          side_effect=mismatch):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                self._publish()
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate(read_consistent_snapshot(self.destination))

    def test_timeout_after_previous_trust_revokes_and_recovers(self):
        from universalddns import supervised_verifier
        self._publish()
        previous = read_consistent_snapshot(self.destination)

        def slow(path, *, timeout_seconds):
            time.sleep(0.12)
            raise ValueError("snapshot unavailable")

        with patch.object(supervised_verifier, "verify_snapshot_supervised",
                          side_effect=slow):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                self._publish(timeout=0.05)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate(previous)
        self.assertEqual(self._publish()["total_records"], 1)

    def test_replacement_during_supervised_read_is_rejected(self):
        from universalddns import supervised_verifier
        original = supervised_verifier.verify_snapshot_supervised

        def replace(path, *, timeout_seconds):
            record = original(path, timeout_seconds=timeout_seconds)
            publish_inventory_snapshot(self.source, self.destination)
            return record

        with patch.object(supervised_verifier, "verify_snapshot_supervised",
                          side_effect=replace):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                self._publish()
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate(read_consistent_snapshot(self.destination))

    def test_invalid_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            publish_with_authorized_child(
                self.source, self.destination, self.registry,
                supervised_verification="yes")


if __name__ == "__main__":
    unittest.main()
