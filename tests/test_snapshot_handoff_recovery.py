"""Bounded, separate-process crash and recovery acceptance tests for handoff.

Uses disposable same-UID processes; cross-UID acceptance lives in its own fixture.
"""
import os
import resource
import signal
import socket
import tempfile
import unittest
from pathlib import Path

from universalddns.snapshot_handoff import receive_snapshot_fd, send_snapshot_fd


class HandoffRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private.db"
        self.path.write_bytes(b"non-sensitive test bytes")
        self.path.chmod(0o600)

    def test_killed_producer_closes_socket_and_recovery_succeeds(self):
        with socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM) as (parent, peer):
            pid = os.fork()
            if pid == 0:
                parent.close()
                # No FD is transferred; this process simulates a stalled producer.
                signal.pause()
                os._exit(2)
            peer.close()
            try:
                os.kill(pid, signal.SIGKILL)
                _, status = os.waitpid(pid, 0)
                self.assertTrue(os.WIFSIGNALED(status))
                with self.assertRaisesRegex(ValueError, "^handoff unavailable$"):
                    receive_snapshot_fd(parent, authorized_uid=os.geteuid(),
                                        producer_uid=os.geteuid())
            finally:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            # A fresh socket is independent of the crashed endpoint.
        with socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM) as (a, b):
            send_snapshot_fd(a, self.path, authorized_uid=os.geteuid())
            fd = receive_snapshot_fd(b, authorized_uid=os.geteuid(),
                                     producer_uid=os.geteuid())
            try:
                self.assertEqual(os.read(fd, 100), b"non-sensitive test bytes")
            finally:
                os.close(fd)

    def test_worker_subprocess_resource_caps_do_not_leak_to_parent(self):
        before = resource.getrlimit(resource.RLIMIT_NOFILE)
        pid = os.fork()
        if pid == 0:
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
                resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
                resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,
                                                       256 * 1024 * 1024))
                assert resource.getrlimit(resource.RLIMIT_NOFILE) == (32, 32)
                assert resource.getrlimit(resource.RLIMIT_CPU) == (3, 3)
                os._exit(0)
            except BaseException:
                os._exit(1)
        _, status = os.waitpid(pid, 0)
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)
        self.assertEqual(resource.getrlimit(resource.RLIMIT_NOFILE), before)


if __name__ == "__main__":
    unittest.main()
