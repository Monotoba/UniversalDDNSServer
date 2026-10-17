"""Isolated parent-authorized child observer acceptance and failure tests."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.authorized_observer import (
    publish_with_authorized_child, read_current_authorized_snapshot,
)
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

        def incorrect_ack(source, destination, connection, nonce):
            try:
                connection.send((nonce, "a" * 32))
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

        def send_then_fail(source, destination, connection, nonce):
            connection.send("a" * 32)
            connection.close()
            os._exit(61)

        with patch.object(authorized_observer, "_publisher_child",
                          side_effect=send_then_fail):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_with_authorized_child(
                    self.source, self.target, self.registry)



    def test_wrong_nonce_and_replayed_ack_fail_closed(self):
        from universalddns import authorized_observer
        for reply in ("wrong-nonce", "replay", "malformed"):
            with self.subTest(reply=reply):
                def malicious(source, destination, connection, nonce):
                    if reply == "wrong-nonce":
                        connection.send(("0" * 64, "a" * 32))
                    elif reply == "replay":
                        connection.send((nonce, "a" * 32))
                        connection.send((nonce, "a" * 32))
                    else:
                        connection.send({"nonce": nonce, "generation": "a" * 32})
                    connection.close()

                with patch.object(authorized_observer, "_publisher_child",
                                  side_effect=malicious):
                    with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                        publish_with_authorized_child(self.source, self.target,
                                                      self.registry)
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    self.registry.validate({"generation": "a" * 32})

    def test_nonce_is_distinct_per_publication(self):
        from universalddns import authorized_observer
        with patch.object(authorized_observer.secrets, "token_hex",
                          side_effect=["a" * 64, "b" * 64]) as generate:
            publish_with_authorized_child(self.source, self.target, self.registry)
            publish_with_authorized_child(self.source, self.target, self.registry)
        self.assertEqual(generate.call_count, 2)

    def test_current_read_refuses_unobserved_external_republication(self):
        from universalddns.inventory_snapshot import publish_inventory_snapshot
        publish_with_authorized_child(self.source, self.target, self.registry)
        old = read_consistent_snapshot(self.target)
        self.assertEqual(
            read_current_authorized_snapshot(self.target, self.registry)["generation"],
            old["generation"])
        # A second publisher does not update the parent's registry.
        publish_inventory_snapshot(self.source, self.target)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_current_authorized_snapshot(self.target, self.registry)
        # The older detached record can still be accepted by the legacy
        # registry, demonstrating why callers need the guarded path read.
        self.registry.validate(old)

    def test_replacement_during_current_read_is_refused(self):
        from universalddns import authorized_observer
        from universalddns.inventory_snapshot import publish_inventory_snapshot
        publish_with_authorized_child(self.source, self.target, self.registry)
        original = authorized_observer.read_consistent_snapshot

        def replace_after_pin(path):
            old = original(path)
            publish_inventory_snapshot(self.source, self.target)
            return old

        with patch.object(authorized_observer, "read_consistent_snapshot",
                          side_effect=replace_after_pin):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                read_current_authorized_snapshot(self.target, self.registry)

    def test_no_snapshot_or_symlink_fails_closed(self):
        publish_with_authorized_child(self.source, self.target, self.registry)
        missing = self.target.with_name("missing.sqlite3")
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_current_authorized_snapshot(missing, self.registry)
        link = self.target.with_name("link.sqlite3")
        link.symlink_to(self.target.name)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            read_current_authorized_snapshot(link, self.registry)

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
