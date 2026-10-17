"""Exercise received descriptor disposal at the low-level SCM_RIGHTS boundary."""
import array
import os
import socket
import tempfile
import unittest
from pathlib import Path

from universalddns.snapshot_handoff import receive_snapshot_fd


class SyntheticMessageChannel:
    """Real Unix peer credentials, deterministic ancillary receive data."""

    def __init__(self, peer, payload, controls, flags=0):
        self.peer = peer
        self.family = peer.family
        self.payload = payload
        self.controls = controls
        self.flags = flags

    def getsockopt(self, *args):
        return self.peer.getsockopt(*args)

    def settimeout(self, seconds):
        self.peer.settimeout(seconds)

    def recvmsg(self, *_args):
        return self.payload, self.controls, self.flags, None


class ReceiveFailureCleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "snapshot.sqlite3"
        self.path.write_bytes(b"snapshot")
        self.path.chmod(0o600)
        self.left, self.right = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(self.left.close)
        self.addCleanup(self.right.close)

    def check_rejection(self, *, payload=b"S", number=1, flags=0,
                        producer_uid=None, writable=False, regular=True):
        origin = os.open(self.path if regular else self.tmp.name,
                         (os.O_RDWR if writable else os.O_RDONLY))
        self.addCleanup(os.close, origin)
        copies = [os.dup(origin) for _ in range(number)]
        rights = array.array("i", copies)
        channel = SyntheticMessageChannel(
            self.right, payload,
            [(socket.SOL_SOCKET, socket.SCM_RIGHTS, rights.tobytes())], flags)
        try:
            with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
                receive_snapshot_fd(
                    channel, authorized_uid=os.geteuid(),
                    producer_uid=(os.geteuid() if producer_uid is None
                                  else producer_uid))
            for fd in copies:
                with self.assertRaises(OSError):
                    os.fstat(fd)
            self.assertGreaterEqual(os.fstat(origin).st_ino, 1)
        finally:
            # If a regression leaves a copy open, clean up the test fixture.
            for fd in copies:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def test_multiple_received_descriptors_are_all_closed(self):
        self.check_rejection(number=2)

    def test_bad_payload_closes_received_descriptor(self):
        self.check_rejection(payload=b"X")

    def test_truncated_ancillary_closes_received_descriptor(self):
        self.check_rejection(flags=socket.MSG_CTRUNC)

    def test_truncated_payload_closes_received_descriptor(self):
        self.check_rejection(flags=socket.MSG_TRUNC)

    def test_unexpected_producer_uid_closes_received_descriptor(self):
        self.check_rejection(producer_uid=os.geteuid() + 1)

    def test_writable_descriptor_is_closed(self):
        self.check_rejection(writable=True)

    def test_directory_descriptor_is_closed(self):
        self.check_rejection(regular=False)


if __name__ == "__main__":
    unittest.main()
