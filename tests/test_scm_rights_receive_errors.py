"""Isolated recvmsg error injection and post-error recovery tests."""
import errno
import os
import socket
import tempfile
import unittest
from pathlib import Path

from universalddns.snapshot_handoff import receive_snapshot_fd, send_snapshot_fd


class ErrorChannel:
    def __init__(self, real, error):
        self.real = real
        self.error = error
        self.family = real.family

    def getsockopt(self, *args):
        return self.real.getsockopt(*args)

    def settimeout(self, value):
        self.real.settimeout(value)

    def recvmsg(self, *args):
        raise self.error


class ReceiveErrorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "snapshot"
        self.path.write_bytes(b"fixture")
        self.path.chmod(0o600)
        self.tx, self.rx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(self.tx.close)
        self.addCleanup(self.rx.close)

    def receive(self, channel):
        return receive_snapshot_fd(
            channel, authorized_uid=os.geteuid(), producer_uid=os.geteuid())

    def test_resource_exhaustion_emfile_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            self.receive(ErrorChannel(self.rx, OSError(errno.EMFILE, "too many open files")))
        self._recover()

    def test_resource_exhaustion_enfile_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            self.receive(ErrorChannel(self.rx, OSError(errno.ENFILE, "file table full")))
        self._recover()

    def test_interrupted_recvmsg_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            self.receive(ErrorChannel(self.rx, InterruptedError(errno.EINTR, "interrupted")))
        self._recover()

    def test_connection_error_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            self.receive(ErrorChannel(self.rx, ConnectionResetError(errno.ECONNRESET, "reset")))
        self._recover()

    def test_repeated_errors_do_not_poison_fresh_receive(self):
        for error in (OSError(errno.EMFILE, "limits"),
                      InterruptedError(errno.EINTR, "signal"),
                      OSError(errno.ENOBUFS, "buffers")) * 3:
            with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
                self.receive(ErrorChannel(self.rx, error))
        self._recover()

    def _recover(self):
        send_snapshot_fd(self.tx, self.path, authorized_uid=os.geteuid())
        fd = self.receive(self.rx)
        try:
            self.assertEqual(os.read(fd, 32), b"fixture")
        finally:
            os.close(fd)


if __name__ == "__main__":
    unittest.main()
