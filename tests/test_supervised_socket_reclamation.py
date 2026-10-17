"""Locally supervised preserved-listener reclamation regression tests."""
import socket
import tempfile
import unittest
from pathlib import Path

from universalddns.owned_unix_listener import OwnedUnixListener
from universalddns.trusted_socket_reclamation import reclaim_closed_owned_listener


class SupervisedReclaimTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.endpoint = self.root / "ipc.sock"

    def test_open_listener_refused_and_remains_connectable(self):
        with OwnedUnixListener(self.root, cleanup_policy="preserve") as listener:
            with self.assertRaisesRegex(ValueError, "listener not safely closed"):
                reclaim_closed_owned_listener(listener, writer_exclusion_established=True)
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(str(self.endpoint))
        self.assertTrue(self.endpoint.exists())

    def test_closed_listener_requires_writer_exclusion_and_allows_restart(self):
        listener = OwnedUnixListener(self.root, cleanup_policy="preserve")
        listener.close()
        with self.assertRaisesRegex(ValueError, "writer exclusion required"):
            reclaim_closed_owned_listener(listener)
        self.assertTrue(self.endpoint.exists())
        self.assertTrue(reclaim_closed_owned_listener(
            listener, writer_exclusion_established=True))
        self.assertFalse(reclaim_closed_owned_listener(
            listener, writer_exclusion_established=True))
        with OwnedUnixListener(self.root):
            pass

    def test_wrong_policy_rejected_without_unlink(self):
        listener = OwnedUnixListener(self.root, cleanup_policy="owned-path")
        listener.close()
        with self.assertRaisesRegex(ValueError, "listener not safely closed"):
            reclaim_closed_owned_listener(listener, writer_exclusion_established=True)

    def test_substituted_socket_remains_untouched(self):
        listener = OwnedUnixListener(self.root, cleanup_policy="preserve")
        listener.close()
        self.endpoint.rename(self.root / "old.sock")
        with socket.socket(socket.AF_UNIX) as substitute:
            substitute.bind(str(self.endpoint))
            expected = self.endpoint.lstat().st_ino
            with self.assertRaisesRegex(ValueError, "socket identity mismatch"):
                reclaim_closed_owned_listener(listener, writer_exclusion_established=True)
            self.assertEqual(self.endpoint.lstat().st_ino, expected)

    def test_unrelated_object_rejected(self):
        with self.assertRaisesRegex(ValueError, "supervised listener required"):
            reclaim_closed_owned_listener(object(), writer_exclusion_established=True)


if __name__ == "__main__":
    unittest.main()
