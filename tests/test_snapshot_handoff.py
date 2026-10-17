"""Local socketpair tests for isolated snapshot descriptor transfer."""
import os
import socket
import tempfile
import unittest
from pathlib import Path

from universalddns.snapshot_handoff import (
    peer_credentials, receive_snapshot_fd, send_snapshot_fd,
)


class SnapshotHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "snapshot.sqlite3"
        self.path.write_bytes(b"fixture only")
        self.path.chmod(0o600)
        self.left, self.right = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(self.left.close)
        self.addCleanup(self.right.close)

    def test_one_read_only_descriptor_transfers(self):
        self.assertEqual(peer_credentials(self.left)[1], os.geteuid())
        send_snapshot_fd(self.left, self.path, authorized_uid=os.geteuid())
        fd = receive_snapshot_fd(self.right, authorized_uid=os.geteuid(),
                                 producer_uid=os.geteuid())
        try:
            self.assertEqual(os.read(fd, 100), b"fixture only")
            with self.assertRaises(OSError):
                os.write(fd, b"not allowed")
        finally:
            os.close(fd)

    def test_unauthorized_sender_does_not_send(self):
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            send_snapshot_fd(self.left, self.path, authorized_uid=os.geteuid() + 1)

    def test_wrong_producer_identity_rejected(self):
        send_snapshot_fd(self.left, self.path, authorized_uid=os.geteuid())
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            receive_snapshot_fd(self.right, authorized_uid=os.geteuid(),
                                producer_uid=os.geteuid() + 1)

    def test_writable_or_invalid_payload_rejected(self):
        self.left.send(b"X")
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            receive_snapshot_fd(self.right, authorized_uid=os.geteuid(),
                                producer_uid=os.geteuid())

    def test_peer_disconnect_fails_closed(self):
        self.left.close()
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            receive_snapshot_fd(self.right, authorized_uid=os.geteuid(),
                                producer_uid=os.geteuid())

    def test_missing_message_times_out(self):
        from unittest.mock import patch
        with patch("universalddns.snapshot_handoff.HANDOFF_TIMEOUT_SECONDS", 0.02):
            with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
                receive_snapshot_fd(self.right, authorized_uid=os.geteuid(),
                                    producer_uid=os.geteuid())

    def test_multiple_rights_rejected_without_descriptor_leak(self):
        import array
        before = len(os.listdir("/proc/self/fd"))
        first = os.open(self.path, os.O_RDONLY)
        second = os.open(self.path, os.O_RDONLY)
        try:
            rights = array.array("i", [first, second])
            self.left.sendmsg([b"S"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                          rights.tobytes())])
            with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
                receive_snapshot_fd(self.right, authorized_uid=os.geteuid(),
                                    producer_uid=os.geteuid())
        finally:
            os.close(first)
            os.close(second)
        self.assertEqual(len(os.listdir("/proc/self/fd")), before)

    def test_duplicate_received_fd_is_not_inheritable(self):
        send_snapshot_fd(self.left, self.path, authorized_uid=os.geteuid())
        fd = receive_snapshot_fd(self.right, authorized_uid=os.geteuid(),
                                 producer_uid=os.geteuid())
        try:
            self.assertFalse(os.get_inheritable(fd))
        finally:
            os.close(fd)

    def test_insecure_permissions_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            send_snapshot_fd(self.left, self.path, authorized_uid=os.geteuid())


if __name__ == "__main__":
    unittest.main()
