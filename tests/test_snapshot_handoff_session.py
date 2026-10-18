"""One-shot challenge and descriptor handoff, disposable AF_UNIX fixtures."""
import os
import socket
import tempfile
import unittest
from pathlib import Path

from universalddns.snapshot_handoff import (
    HandoffSession, receive_snapshot_fd, send_snapshot_fd,
)


class SessionBoundHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private"
        self.path.write_bytes(b"fixture")
        self.path.chmod(0o600)
        self.left, self.right = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(self.left.close)
        self.addCleanup(self.right.close)

    def send(self, challenge):
        send_snapshot_fd(self.left, self.path, authorized_uid=os.geteuid(),
                         authorized_pid=os.getpid(), session_challenge=challenge)

    def receive(self, session):
        return receive_snapshot_fd(
            self.right, authorized_uid=os.geteuid(),
            producer_uid=os.geteuid(), authorized_pid=os.getpid(), session=session)

    def test_matching_challenge_one_shot(self):
        session = HandoffSession()
        self.send(session.challenge)
        fd = self.receive(session)
        try:
            self.assertEqual(os.read(fd, 20), b"fixture")
        finally:
            os.close(fd)
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            self.receive(session)

    def test_wrong_challenge_burns_session_and_closes_received_fd(self):
        session = HandoffSession()
        before = len(os.listdir("/proc/self/fd"))
        self.send(b"0" * 32)
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            self.receive(session)
        self.assertEqual(len(os.listdir("/proc/self/fd")), before)
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            self.receive(session)

    def test_replayed_transfer_refused_even_with_matching_bytes(self):
        session = HandoffSession()
        self.send(session.challenge)
        first = self.receive(session)
        os.close(first)
        self.send(session.challenge)
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            self.receive(session)

    def test_new_session_rejects_stale_challenge(self):
        old = HandoffSession()
        fresh = HandoffSession()
        self.send(old.challenge)
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            self.receive(fresh)

    def test_invalid_challenge_is_refused_before_send(self):
        for challenge in (b"small", "x" * 32, True, b"x" * 33):
            with self.subTest(challenge=challenge):
                with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
                    self.send(challenge)


if __name__ == "__main__":
    unittest.main()
