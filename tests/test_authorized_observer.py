"""Isolated parent-authorized child observer acceptance and failure tests."""
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
                     "requires fork-enabled POSIX")
class AuthorizedObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "live.db"
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

    def test_authorized_child_ack_matches_snapshot(self):
        result = publish_with_authorized_child(
            self.source, self.target, self.registry)
        self.assertEqual(result["total_records"], 1)
        self.registry.validate(read_consistent_snapshot(self.target))

    def test_failed_child_revokes_previously_issued_generation(self):
        publish_with_authorized_child(self.source, self.target, self.registry)
        old = read_consistent_snapshot(self.target)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            publish_with_authorized_child(
                self.source.with_name("missing.sqlite3"),
                self.target, self.registry, timeout_seconds=2)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate(old)

    def test_bad_generation_from_authorized_child_is_rejected(self):
        from universalddns import authorized_observer
        actual = authorized_observer._publisher_child

        def incorrect_ack(source, destination, connection):
            try:
                connection.send("a" * 32)
            finally:
                connection.close()

        with patch.object(authorized_observer, "_publisher_child",
                          side_effect=incorrect_ack):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_with_authorized_child(
                    self.source, self.target, self.registry)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.registry.validate({"generation": "a" * 32})

    def test_child_exits_after_ack_is_not_trusted(self):
        from universalddns import authorized_observer

        def send_then_fail(source, destination, connection):
            connection.send("a" * 32)
            connection.close()
            os._exit(61)

        with patch.object(authorized_observer, "_publisher_child",
                          side_effect=send_then_fail):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_with_authorized_child(
                    self.source, self.target, self.registry)

    def test_invalid_timeout_fails_without_child(self):
        for invalid in (0, -1, float("inf"), "bad", True, 31):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    publish_with_authorized_child(
                        self.source, self.target, self.registry,
                        timeout_seconds=invalid)

    def test_distinct_parent_registry_does_not_inherit_child_issuance(self):
        publish_with_authorized_child(self.source, self.target, self.registry)
        snapshot = read_consistent_snapshot(self.target)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            SnapshotIssuanceRegistry().validate(snapshot)


if __name__ == "__main__":
    unittest.main()
