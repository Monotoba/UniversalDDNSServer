"""Isolated bounded registry and Linux pidfd lifecycle checks."""
import os
import select
import signal
import tempfile
import unittest
from pathlib import Path

from universalddns.listener_holder_registry import ListenerHolderRegistry
from universalddns.owned_unix_listener import OwnedUnixListener


class HolderRegistryContractTests(unittest.TestCase):
    def test_capacity_and_duplicate_pid_rejected(self):
        registry = ListenerHolderRegistry(max_holders=1)
        registry.register(123, 9)
        with self.assertRaises(ValueError):
            registry.register(123, 10)
        with self.assertRaises(ValueError):
            registry.register(124, 11)

    def test_seal_requires_entries_and_rejects_mutation(self):
        registry = ListenerHolderRegistry()
        with self.assertRaises(ValueError):
            registry.seal()
        registry.register(123, 9)
        registry.seal()
        with self.assertRaises(ValueError):
            registry.register(124, 10)
        with self.assertRaisesRegex(ValueError, "holder registry incomplete"):
            registry.reclaim(".", (1, 2), owner_pid=124)

    def test_invalid_capacity_and_registration(self):
        for value in (0, 65, True, "8"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ListenerHolderRegistry(max_holders=value)
        registry = ListenerHolderRegistry()
        for pid, fd in ((0, 4), (True, 3), (2, -1), (4, False)):
            with self.subTest(pid=pid, fd=fd), self.assertRaises(ValueError):
                registry.register(pid, fd)


@unittest.skipUnless(hasattr(os, "pidfd_open") and hasattr(os, "fork"),
                     "Linux pidfd required")
class HolderRegistryLifecycleTests(unittest.TestCase):
    def test_sealed_registry_refuses_live_holder_then_recovers(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            listener = OwnedUnixListener(directory, cleanup_policy="preserve")
            stat = (directory / "ipc.sock").lstat()
            identity = (stat.st_dev, stat.st_ino)
            child = os.fork()
            if child == 0:
                signal.pause()
                os._exit(0)
            pidfd = os.pidfd_open(child)
            registry = ListenerHolderRegistry(max_holders=2)
            registry.register(child, pidfd)
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
                poller.register(pidfd, select.POLLIN)
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
                os.close(pidfd)


if __name__ == "__main__":
    unittest.main()
