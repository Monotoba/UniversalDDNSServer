"""Isolated owned pidfd registry contracts and lifecycle regression tests."""
import os
import select
import signal
import tempfile
import unittest
from pathlib import Path

from universalddns.listener_holder_registry import ListenerHolderRegistry
from universalddns.owned_unix_listener import OwnedUnixListener


@unittest.skipUnless(hasattr(os, "pidfd_open"), "requires Linux pidfd")
class HolderRegistryContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = ListenerHolderRegistry(max_holders=1)
        self.addCleanup(self.registry.close)
        self.pid = os.getpid()
        self.source_fd = os.pidfd_open(self.pid)
        self.addCleanup(os.close, self.source_fd)

    def test_capacity_and_duplicate_pid_rejected(self):
        self.registry.register(self.pid, self.source_fd)
        with self.assertRaises(ValueError):
            self.registry.register(self.pid, self.source_fd)
        with self.assertRaises(ValueError):
            self.registry.register(self.pid + 1, self.source_fd)

    def test_seal_requires_entries_and_rejects_mutation(self):
        with self.assertRaises(ValueError):
            self.registry.seal()
        self.registry.register(self.pid, self.source_fd)
        self.registry.seal()
        with self.assertRaises(ValueError):
            self.registry.register(self.pid + 1, self.source_fd)
        with self.assertRaisesRegex(ValueError, "holder registry incomplete"):
            self.registry.reclaim(".", (1, 2), owner_pid=self.pid + 1)

    def test_invalid_capacity_and_registration(self):
        for value in (0, 65, True, "8"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ListenerHolderRegistry(max_holders=value)
        for pid, fd in ((0, self.source_fd), (True, self.source_fd),
                        (self.pid, -1), (self.pid, False),
                        (self.pid + 1, self.source_fd)):
            with self.subTest(pid=pid, fd=fd), self.assertRaises(ValueError):
                self.registry.register(pid, fd)

    def test_caller_closure_and_fd_reuse_do_not_change_owned_pin(self):
        self.registry.register(self.pid, self.source_fd)
        owned = self.registry._holders[self.pid]
        self.assertNotEqual(owned, self.source_fd)
        self.assertFalse(os.get_inheritable(owned))
        os.close(self.source_fd)
        # Occupy the caller's former number with a non-pidfd descriptor.
        with open(os.devnull, "rb") as devnull:
            os.dup2(devnull.fileno(), self.source_fd)
            self.registry.seal()
            with self.assertRaisesRegex(ValueError, "listener exit unverified"):
                self.registry.reclaim(".", (1, 2), owner_pid=self.pid,
                                      writer_exclusion_established=True)
            self.assertEqual(os.fstat(owned).st_ino, os.fstat(owned).st_ino)
        # Restore an open fd for cleanup registered by setUp.
        os.dup2(owned, self.source_fd)

    def test_repeated_close_frees_owned_fd_and_rejects_use(self):
        self.registry.register(self.pid, self.source_fd)
        owned = self.registry._holders[self.pid]
        self.registry.close()
        self.registry.close()
        with self.assertRaises(OSError):
            os.fstat(owned)
        with self.assertRaisesRegex(ValueError, "holder registry closed"):
            self.registry.register(self.pid, self.source_fd)
        with self.assertRaisesRegex(ValueError, "holder registry closed"):
            self.registry.seal()
        with self.assertRaisesRegex(ValueError, "holder registry closed"):
            self.registry.reclaim(".", (1, 2), owner_pid=self.pid)


@unittest.skipUnless(hasattr(os, "pidfd_open") and hasattr(os, "fork"),
                     "Linux pidfd required")
class HolderRegistryLifecycleTests(unittest.TestCase):
    def test_sealed_registry_refuses_live_holder_then_recovers(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            listener = OwnedUnixListener(directory, cleanup_policy="preserve")
            info = (directory / "ipc.sock").lstat()
            identity = (info.st_dev, info.st_ino)
            child = os.fork()
            if child == 0:
                signal.pause()
                os._exit(0)
            pidfd = os.pidfd_open(child)
            registry = ListenerHolderRegistry(max_holders=2)
            registry.register(child, pidfd)
            os.close(pidfd)
            listener.close()
            try:
                with self.assertRaisesRegex(ValueError, "holder registry incomplete"):
                    registry.reclaim(directory, identity, owner_pid=child,
                                     writer_exclusion_established=True)
                registry.seal()
                with self.assertRaisesRegex(ValueError, "listener exit unverified"):
                    registry.reclaim(directory, identity, owner_pid=child,
                                     writer_exclusion_established=True)
                self.assertTrue((directory / "ipc.sock").exists())
                os.kill(child, signal.SIGKILL)
                poller = select.poll()
                poller.register(registry._holders[child], select.POLLIN)
                self.assertTrue(poller.poll(5000))
                self.assertTrue(registry.reclaim(
                    directory, identity, owner_pid=child,
                    writer_exclusion_established=True))
                with OwnedUnixListener(directory):
                    pass
            finally:
                try:
                    os.kill(child, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.waitpid(child, 0)
                registry.close()


if __name__ == "__main__":
    unittest.main()
