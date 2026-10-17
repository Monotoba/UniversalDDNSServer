"""Parent-issued trust requires an authenticated descriptor stage."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.authorized_observer import publish_with_authorized_child
from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork"),
                     "requires Linux AF_UNIX fork")
class AuthorizedHandoffChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source.sqlite3"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.destination = private / "snapshot.sqlite3"
        self.registry = SnapshotIssuanceRegistry()
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))

    def publish(self):
        return publish_with_authorized_child(
            self.source, self.destination, self.registry,
            descriptor_handoff=True)

    def test_complete_chain_issues_only_after_verified_descriptor(self):
        result = self.publish()
        self.assertEqual(result["total_records"], 1)
        self.registry.validate(read_consistent_snapshot(self.destination))

    def test_sender_crash_revokes_previous_issuance_and_recovers(self):
        from universalddns import authorized_handoff_chain
        self.publish()
        old = read_consistent_snapshot(self.destination)
        def crash(*args):
            os._exit(76)
        with patch.object(authorized_handoff_chain, "_handoff_sender",
                          side_effect=crash):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                self.publish()
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate(old)
        self.assertEqual(self.publish()["total_records"], 1)

    def test_wrong_challenge_and_wrong_descriptor_prevent_issuance(self):
        from universalddns import authorized_handoff_chain
        original = authorized_handoff_chain._handoff_sender
        for mode in ("challenge", "descriptor"):
            with self.subTest(mode=mode):
                def wrong(address, destination, challenge, parent_pid):
                    if mode == "challenge":
                        return original(address, destination, b"0" * 32, parent_pid)
                    replacement = str(self.destination.parent / "replacement.sqlite3")
                    from universalddns.inventory_snapshot import publish_inventory_snapshot
                    publish_inventory_snapshot(self.source, replacement)
                    return original(address, replacement, challenge, parent_pid)
                with patch.object(authorized_handoff_chain, "_handoff_sender",
                                  side_effect=wrong):
                    with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                        self.publish()
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    self.registry.validate({"generation": "a" * 32)

    def test_default_legacy_path_and_invalid_mode(self):
        self.assertEqual(publish_with_authorized_child(
            self.source, self.destination, self.registry)["total_records"], 1)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            publish_with_authorized_child(
                self.source, self.destination, self.registry,
                descriptor_handoff="enabled")


if __name__ == "__main__":
    unittest.main()
