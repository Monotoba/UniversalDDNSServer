"""Deterministic Linux inherited-listener descriptor lifecycle tests."""
import os
import select
import signal
import tempfile
import unittest
from pathlib import Path

from universalddns.owned_unix_listener import OwnedUnixListener
from universalddns.pidfd_socket_reclamation import reclaim_exited_listener_socket


@unittest.skipUnless(hasattr(os, "pidfd_open") and hasattr(os, "fork"),
                     "requires Linux pidfds")
class InheritedListenerHolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.endpoint = self.root / "ipc.sock"

    def test_exited_owner_cannot_reclaim_while_inherited_holder_lives(self):
        server = OwnedUnixListener(self.root, cleanup_policy="preserve")
        meta = self.endpoint.lstat()
        identity = (meta.st_dev, meta.st_ino)
        ready_read, ready_write = os.pipe()
        owner = os.fork()
        if owner == 0:
            os.close(ready_read)
            os.close(ready_write)
            signal.pause()
            os._exit(0)
        ownerfd = os.pidfd_open(owner)
        holder = os.fork()
        if holder == 0:
            os.close(ready_read)
            try:
                os.write(ready_write, b"R")
                os.close(ready_write)
                signal.pause()
            except BaseException:
                os._exit(2)
            os._exit(0)
        holderfd = os.pidfd_open(holder)
        os.close(ready_write)
        try:
            self.assertEqual(os.read(ready_read, 1), b"R")
            server.close()
            os.kill(owner, signal.SIGKILL)
            poller = select.poll()
            poller.register(ownerfd, select.POLLIN)
            self.assertTrue(poller.poll(5000))
            with self.assertRaisesRegex(ValueError, "listener exit unverified"):
                reclaim_exited_listener_socket(
                    self.root, identity, expected_pid=owner,
                    listener_pidfd=ownerfd, writer_exclusion_established=True,
                    additional_holder_pidfds=((holder, holderfd),))
            self.assertTrue(self.endpoint.exists())
            os.kill(holder, signal.SIGKILL)
            poller = select.poll()
            poller.register(holderfd, select.POLLIN)
            self.assertTrue(poller.poll(5000))
            self.assertTrue(reclaim_exited_listener_socket(
                self.root, identity, expected_pid=owner,
                listener_pidfd=ownerfd, writer_exclusion_established=True,
                additional_holder_pidfds=((holder, holderfd),)))
            with OwnedUnixListener(self.root):
                pass
        finally:
            for pid in (owner, holder):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.waitpid(pid, 0)
            os.close(ready_read)
            os.close(ownerfd)
            os.close(holderfd)
            server.close()

    def test_invalid_holder_identity_fails_closed(self):
        server = OwnedUnixListener(self.root, cleanup_policy="preserve")
        meta = self.endpoint.lstat()
        identity = (meta.st_dev, meta.st_ino)
        child = os.fork()
        if child == 0:
            signal.pause()
            os._exit(0)
        fd = os.pidfd_open(child)
        server.close()
        try:
            os.kill(child, signal.SIGKILL)
            poller = select.poll()
            poller.register(fd, select.POLLIN)
            self.assertTrue(poller.poll(5000))
            for holders in (((child + 1, fd),), ((child, -1),), ((child,),)):
                with self.subTest(holders=holders):
                    with self.assertRaisesRegex(ValueError, "listener exit unverified"):
                        reclaim_exited_listener_socket(
                            self.root, identity, expected_pid=child,
                            listener_pidfd=fd, writer_exclusion_established=True,
                            additional_holder_pidfds=holders)
                    self.assertTrue(self.endpoint.exists())
        finally:
            os.waitpid(child, 0)
            os.close(fd)


if __name__ == "__main__":
    unittest.main()
