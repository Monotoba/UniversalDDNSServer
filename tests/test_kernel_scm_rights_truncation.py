"""Real Linux AF_UNIX SCM_RIGHTS truncation and rejection acceptance tests."""
import array
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path

from universalddns.snapshot_handoff import receive_snapshot_fd


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux ancillary ABI required")
class KernelAncillaryRejectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "snapshot"
        self.path.write_bytes(b"fixture")
        self.path.chmod(0o600)
        self.tx, self.rx = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(self.tx.close)
        self.addCleanup(self.rx.close)

    def _transmit(self, payload, n=1):
        originals = [os.open(self.path, os.O_RDONLY) for _ in range(n)]
        try:
            self.tx.sendmsg([payload], [(
                socket.SOL_SOCKET, socket.SCM_RIGHTS,
                array.array("i", originals).tobytes())])
        finally:
            for fd in originals:
                os.close(fd)

    def _reject_and_check_open(self):
        # Compare FD target identities, not numeric descriptor counts. This
        # catches kernel-delivered leaked copies even if other FDs close.
        def targets():
            found = set()
            for entry in os.listdir("/proc/self/fd"):
                try:
                    target = os.readlink(f"/proc/self/fd/{entry}")
                except FileNotFoundError:
                    continue
                if target == str(self.path):
                    found.add(int(entry))
            return found

        original = os.open(self.path, os.O_RDONLY)
        try:
            before = targets()
            with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
                receive_snapshot_fd(
                    self.rx, authorized_uid=os.geteuid(),
                    producer_uid=os.geteuid())
            self.assertEqual(targets(), before)
            self.assertEqual(os.fstat(original).st_ino, self.path.stat().st_ino)
        finally:
            os.close(original)

    def test_kernel_ancillary_truncation_closes_received_fds(self):
        self._transmit(b"S", n=16)
        self._reject_and_check_open()

    def test_kernel_multiple_rights_closes_received_fds(self):
        self._transmit(b"S", n=3)
        self._reject_and_check_open()

    def test_kernel_bad_payload_closes_received_fd(self):
        self._transmit(b"X", n=1)
        self._reject_and_check_open()

    def test_kernel_payload_truncation_closes_received_fd(self):
        self._transmit(b"S" + b"Z" * 256, n=1)
        self._reject_and_check_open()

    def test_kernel_truncation_flag_is_observed(self):
        self._transmit(b"S", n=16)
        observed = []
        real_recvmsg = self.rx.recvmsg

        class RecordingSocket:
            family = socket.AF_UNIX

            def getsockopt(self, *args):
                return self_socket.getsockopt(*args)

            def settimeout(self, timeout):
                self_socket.settimeout(timeout)

            def recvmsg(self, *args):
                result = real_recvmsg(*args)
                observed.append(result[2])
                return result

        self_socket = self.rx
        with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
            receive_snapshot_fd(
                RecordingSocket(), authorized_uid=os.geteuid(),
                producer_uid=os.geteuid())
        self.assertEqual(len(observed), 1)
        self.assertTrue(observed[0] & socket.MSG_CTRUNC)


if __name__ == "__main__":
    unittest.main()
