"""Real Linux cross-process AF_UNIX peer-credential and descriptor acceptance."""
import os
import socket
import tempfile
import unittest
import uuid
from pathlib import Path

from universalddns.snapshot_handoff import (
    peer_credentials, receive_snapshot_fd, send_snapshot_fd,
)


@unittest.skipUnless(hasattr(socket, "SO_PEERCRED") and hasattr(os, "fork"),
                     "Linux SO_PEERCRED and fork required")
class PeerIdentityHandoffTests(unittest.TestCase):
    def test_live_child_peer_pid_bound_to_descriptor(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "snapshot.sqlite3"
            snapshot.write_bytes(b"trusted fixture only")
            snapshot.chmod(0o600)
            address = "\\x00uddns-peer-" + uuid.uuid4().hex
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(address)
                listener.listen(1)
                listener.settimeout(6)
                parent_pid = os.getpid()
                child_pid = os.fork()
                if child_pid == 0:
                    try:
                        listener.close()
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                            peer.settimeout(5)
                            peer.connect(address)
                            if peer_credentials(peer)[0] != parent_pid:
                                raise AssertionError("wrong parent PID")
                            with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
                                send_snapshot_fd(peer, snapshot, authorized_uid=os.geteuid(),
                                                 authorized_pid=parent_pid + 99999)
                            send_snapshot_fd(peer, snapshot, authorized_uid=os.geteuid(),
                                             authorized_pid=parent_pid)
                        os._exit(0)
                    except BaseException:
                        os._exit(2)
                try:
                    with listener.accept()[0] as channel:
                        channel.settimeout(5)
                        self.assertEqual(peer_credentials(channel)[0], child_pid)
                        # Rejected identity must not consume the queued descriptor.
                        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
                            receive_snapshot_fd(channel, authorized_uid=os.geteuid(),
                                                producer_uid=os.geteuid(),
                                                authorized_pid=child_pid + 99999)
                        fd = receive_snapshot_fd(
                            channel, authorized_uid=os.geteuid(),
                            producer_uid=os.geteuid(), authorized_pid=child_pid)
                        try:
                            self.assertEqual(os.read(fd, 100), b"trusted fixture only")
                            self.assertFalse(os.get_inheritable(fd))
                            with self.assertRaises(OSError):
                                os.write(fd, b"x")
                        finally:
                            os.close(fd)
                finally:
                    _, status = os.waitpid(child_pid, 0)
                    self.assertTrue(os.WIFEXITED(status))
                    self.assertEqual(os.WEXITSTATUS(status), 0)

    def test_rejects_invalid_optional_peer_pid(self):
        with socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM) as pair:
            left, right = pair
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "private"
                path.write_bytes(b"test")
                path.chmod(0o600)
                for invalid in (0, -1, True, "123", 1.5):
                    with self.subTest(value=invalid):
                        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
                            send_snapshot_fd(left, path, authorized_uid=os.geteuid(),
                                             authorized_pid=invalid)
                        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
                            receive_snapshot_fd(right, authorized_uid=os.geteuid(),
                                                producer_uid=os.geteuid(),
                                                authorized_pid=invalid)


if __name__ == "__main__":
    unittest.main()
