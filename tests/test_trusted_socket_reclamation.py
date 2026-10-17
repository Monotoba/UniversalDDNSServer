"""Isolated trusted socket coordinator recovery contract."""
import socket
import tempfile
import unittest
from pathlib import Path

from universalddns.owned_unix_listener import OwnedUnixListener
from universalddns.trusted_socket_reclamation import reclaim_preserved_socket


class TrustedSocketReclamationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sock = self.root / "ipc.sock"

    def preserved(self):
        server = OwnedUnixListener(self.root, cleanup_policy="preserve")
        entry = self.sock.lstat()
        identity = (entry.st_dev, entry.st_ino)
        server.close()
        return identity

    def test_explicit_trusted_reclamation_allows_restart(self):
        identity = self.preserved()
        with self.assertRaisesRegex(ValueError, "writer exclusion required"):
            reclaim_preserved_socket(self.root, identity)
        self.assertTrue(self.sock.exists())
        self.assertTrue(reclaim_preserved_socket(
            self.root, identity, writer_exclusion_established=True))
        self.assertFalse(reclaim_preserved_socket(
            self.root, identity, writer_exclusion_established=True))
        with OwnedUnixListener(self.root):
            pass

    def test_replaced_socket_is_preserved(self):
        identity = self.preserved()
        self.sock.rename(self.root / "old.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as impostor:
            impostor.bind(str(self.sock))
            after = self.sock.lstat()
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                reclaim_preserved_socket(
                    self.root, identity, writer_exclusion_established=True)
            self.assertEqual(after.st_ino, self.sock.lstat().st_ino)

    def test_regular_file_and_symlink_never_removed(self):
        identity = self.preserved()
        self.sock.unlink()
        self.sock.write_text("sentinel")
        with self.assertRaises(ValueError):
            reclaim_preserved_socket(self.root, identity, writer_exclusion_established=True)
        self.assertEqual(self.sock.read_text(), "sentinel")
        self.sock.unlink()
        self.sock.symlink_to("absent")
        with self.assertRaises(ValueError):
            reclaim_preserved_socket(self.root, identity, writer_exclusion_established=True)
        self.assertTrue(self.sock.is_symlink())

    def test_invalid_identity_and_permission_drift_fail_closed(self):
        identity = self.preserved()
        with self.assertRaises(ValueError):
            reclaim_preserved_socket(self.root, (identity[0], -1),
                                     writer_exclusion_established=True)
        self.root.chmod(0o755)
        try:
            with self.assertRaisesRegex(ValueError, "untrusted socket directory"):
                reclaim_preserved_socket(self.root, identity,
                                         writer_exclusion_established=True)
            self.assertTrue(self.sock.exists())
        finally:
            self.root.chmod(0o700)

    def test_parent_replacement_does_not_unlink_substitute(self):
        identity = self.preserved()
        original = self.root.with_name(self.root.name + "-moved")
        self.root.rename(original)
        self.root.mkdir(mode=0o700)
        target = self.root / "ipc.sock"
        target.write_text("substitute")
        try:
            with self.assertRaises(ValueError):
                reclaim_preserved_socket(self.root, identity,
                                         writer_exclusion_established=True)
            self.assertEqual(target.read_text(), "substitute")
        finally:
            target.unlink()
            self.root.rmdir()
            original.rename(self.root)

if __name__ == "__main__":
    unittest.main()
