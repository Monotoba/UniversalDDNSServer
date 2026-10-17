"""Disposable Linux pidfd-gated preserved socket reclamation."""
import os
import select
import signal
import socket
import tempfile
import unittest
from pathlib import Path

from universalddns.owned_unix_listener import OwnedUnixListener
from universalddns.pidfd_socket_reclamation import reclaim_exited_listener_socket


@unittest.skipUnless(hasattr(os, "pidfd_open") and hasattr(os, "fork"),
                     "Linux pidfd required")
class PidfdSocketReclamationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "ipc.sock"

    def spawn(self):
        readfd, writefd = os.pipe()
        child = os.fork()
        if child == 0:
            os.close(readfd)
            try:
                listener = OwnedUnixListener(self.root, cleanup_policy="preserve")
                entry = self.path.lstat()
                os.write(writefd, f"{entry.st_dev}:{entry.st_ino}".encode())
                os.close(writefd)
                signal.pause()
                listener.close()
            except BaseException:
                os._exit(2)
            os._exit(0)
        os.close(writefd)
        payload = os.read(readfd, 100)
        os.close(readfd)
        if not payload:
            os.waitpid(child, 0)
            self.fail("child did not bind")
        return child, os.pidfd_open(child), tuple(map(int, payload.decode().split(":")))

    def test_live_pidfd_refused_then_exit_allows_reclaim_and_restart(self):
        pid, fd, identity = self.spawn()
        try:
            with self.assertRaisesRegex(ValueError, "writer exclusion required"):
                reclaim_exited_listener_socket(self.root, identity,
                    expected_pid=pid, listener_pidfd=fd)
            with self.assertRaisesRegex(ValueError, "listener exit unverified"):
                reclaim_exited_listener_socket(self.root, identity,
                    expected_pid=pid, listener_pidfd=fd,
                    writer_exclusion_established=True)
            self.assertTrue(self.path.exists())
        finally:
            os.kill(pid, signal.SIGKILL)
            watcher = select.poll()
            watcher.register(fd, select.POLLIN)
            self.assertTrue(watcher.poll(5000))
        try:
            self.assertTrue(reclaim_exited_listener_socket(self.root, identity,
                expected_pid=pid, listener_pidfd=fd,
                writer_exclusion_established=True))
            self.assertFalse(reclaim_exited_listener_socket(self.root, identity,
                expected_pid=pid, listener_pidfd=fd,
                writer_exclusion_established=True))
            with OwnedUnixListener(self.root):
                pass
        finally:
            os.waitpid(pid, 0)
            os.close(fd)

    def test_unrelated_pidfd_and_invalid_fd_preserve_endpoint(self):
        pid, fd, identity = self.spawn()
        other = os.pidfd_open(os.getpid())
        try:
            with self.assertRaisesRegex(ValueError, "listener exit unverified"):
                reclaim_exited_listener_socket(self.root, identity,
                    expected_pid=pid, listener_pidfd=other,
                    writer_exclusion_established=True)
            with self.assertRaisesRegex(ValueError, "listener exit unverified"):
                reclaim_exited_listener_socket(self.root, identity,
                    expected_pid=pid, listener_pidfd=-1,
                    writer_exclusion_established=True)
            self.assertTrue(self.path.exists())
        finally:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            os.close(other)
            os.close(fd)

    def test_exited_pidfd_cannot_authorize_replacement(self):
        pid, fd, identity = self.spawn()
        os.kill(pid, signal.SIGKILL)
        watcher = select.poll()
        watcher.register(fd, select.POLLIN)
        self.assertTrue(watcher.poll(5000))
        try:
            self.path.rename(self.root / "old.sock")
            with socket.socket(socket.AF_UNIX) as imposter:
                imposter.bind(str(self.path))
                inode = self.path.lstat().st_ino
                with self.assertRaisesRegex(ValueError, "socket identity mismatch"):
                    reclaim_exited_listener_socket(self.root, identity,
                        expected_pid=pid, listener_pidfd=fd,
                        writer_exclusion_established=True)
                self.assertEqual(inode, self.path.lstat().st_ino)
        finally:
            os.waitpid(pid, 0)
            os.close(fd)


if __name__ == "__main__":
    unittest.main()
