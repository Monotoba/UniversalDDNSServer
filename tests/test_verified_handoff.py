"""Session-bound descriptor verification; transfer does not grant issuance."""
import os
import socket
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns import verified_handoff

from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.inventory_snapshot import publish_inventory_snapshot
from universalddns.snapshot_handoff import HandoffSession, send_snapshot_fd
from universalddns.verified_handoff import receive_verified_snapshot


class VerifiedHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source.sqlite3"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.target = private / "inventory.sqlite3"
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))
        publish_inventory_snapshot(self.source, self.target)
        self.left, self.right = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(self.left.close)
        self.addCleanup(self.right.close)

    def transfer(self, session, *, path=None, expected=None, identity=None):
        send_snapshot_fd(self.left, self.target if path is None else path,
                         authorized_uid=os.geteuid(),
                         session_challenge=session.challenge)
        return receive_verified_snapshot(
            self.right, authorized_uid=os.geteuid(), producer_uid=os.geteuid(),
            session=session, expected_generation=(
                read_consistent_snapshot(self.target)["generation"]
                if expected is None else expected),
            expected_identity=identity)

    def test_matching_generation_and_inode_consumes_session(self):
        session = HandoffSession()
        info = self.target.stat()
        result = self.transfer(session, identity=(info.st_dev, info.st_ino))
        self.assertEqual(result["total_records"], 1)
        self.assertTrue(session.consumed)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            receive_verified_snapshot(
                self.right, authorized_uid=os.geteuid(),
                producer_uid=os.geteuid(), session=session,
                expected_generation=result["generation"])

    def test_stale_generation_fails_closed_and_no_fd_leak(self):
        session = HandoffSession()
        captured = []
        actual_read = verified_handoff.read_snapshot_fd

        def inspect_received(fd, *, trusted_producer_uid):
            captured.append(fd)
            return actual_read(fd, trusted_producer_uid=trusted_producer_uid)

        with patch.object(verified_handoff, "read_snapshot_fd",
                          side_effect=inspect_received):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                self.transfer(session, expected="a" * 32)
        self.assertTrue(session.consumed)
        self.assertEqual(len(captured), 1)
        with self.assertRaises(OSError):
            os.fstat(captured[0])

    def test_successful_handoff_closes_only_received_descriptor(self):
        session = HandoffSession()
        captured = []
        actual_read = verified_handoff.read_snapshot_fd
        reference = os.open(self.target, os.O_RDONLY)
        self.addCleanup(os.close, reference)

        def inspect_received(fd, *, trusted_producer_uid):
            captured.append(fd)
            return actual_read(fd, trusted_producer_uid=trusted_producer_uid)

        with patch.object(verified_handoff, "read_snapshot_fd",
                          side_effect=inspect_received):
            result = self.transfer(session)
        self.assertEqual(result["total_records"], 1)
        self.assertTrue(session.consumed)
        self.assertEqual(len(captured), 1)
        with self.assertRaises(OSError):
            os.fstat(captured[0])
        self.assertEqual(os.fstat(reference).st_ino, self.target.stat().st_ino)

    def test_different_inventories_cannot_substitute_descriptor(self):
        alternate = self.target.with_name("other.sqlite3")
        publish_inventory_snapshot(self.source, alternate)
        session = HandoffSession()
        expected = read_consistent_snapshot(self.target)["generation"]
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.transfer(session, path=alternate, expected=expected)
        self.assertTrue(session.consumed)

    def test_matching_generation_rejects_wrong_inode(self):
        session = HandoffSession()
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.transfer(session, identity=(0, 0))
        self.assertTrue(session.consumed)

    def test_invalid_expectations_burn_challenge(self):
        for bad in ("not-uuid", True, "f" * 33):
            with self.subTest(bad=bad):
                session = HandoffSession()
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    receive_verified_snapshot(
                        self.right, authorized_uid=os.geteuid(),
                        producer_uid=os.geteuid(), session=session,
                        expected_generation=bad)
                self.assertTrue(session.consumed)


if __name__ == "__main__":
    unittest.main()
