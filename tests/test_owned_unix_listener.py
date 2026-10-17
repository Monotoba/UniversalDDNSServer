"""Owned private listener lifecycle and restart tests."""
import os
import signal
import socket
import stat
import tempfile
import unittest
from pathlib import Path

from universalddns.owned_unix_listener import OwnedUnixListener


class OwnedListenerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "ipc.sock"

    def test_graceful_shutdown_closes_clients_and_allows_restart(self):
        with OwnedUnixListener(self.root) as server:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            with client:
                client.connect(str(self.path))
                accepted = server.listener.accept()
                self.assertEqual(server.listener.active_count, 1)
                self.assertTrue(stat.S_ISSOCK(self.path.lstat().st_mode))
                self.assertGreaterEqual(accepted.fileno(), 0)
        self.assertFalse(self.path.exists())
        self.assertEqual(accepted.fileno(), -1)
        with OwnedUnixListener(self.root) as restarted:
            self.assertTrue(self.path.exists())
            self.assertEqual(restarted.listener.active_count, 0)
        self.assertFalse(self.path.exists())

    def test_existing_endpoint_and_symlink_refused_without_unlink(self):
        self.path.write_text("untrusted", encoding="ascii")
        with self.assertRaises(OSError):
            OwnedUnixListener(self.root)
        self.assertEqual(self.path.read_text(encoding="ascii"), "untrusted")
        self.path.unlink()
        other = self.root / "outside"
        other.write_text("safe", encoding="ascii")
        self.path.symlink_to(other)
        with self.assertRaises(OSError):
            OwnedUnixListener(self.root)
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(other.read_text(encoding="ascii"), "safe")

    def test_path_replacement_never_removed_during_shutdown(self):
        server = OwnedUnixListener(self.root)
        former = self.root / "old.sock"
        self.path.rename(former)
        self.path.write_text("new occupant", encoding="ascii")
        server.close()
        self.assertEqual(self.path.read_text(encoding="ascii"), "new occupant")
        self.assertTrue(former.exists())
        former.unlink()
        self.path.unlink()
        with OwnedUnixListener(self.root):
            pass

    def test_replaced_parent_directory_cannot_redirect_shutdown_unlink(self):
        server = OwnedUnixListener(self.root)
        original = self.root.with_name(self.root.name + "-original")
        self.root.rename(original)
        self.root.mkdir(mode=0o700)
        replacement = self.root / "ipc.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as impostor:
            impostor.bind(str(replacement))
            impostor.listen(1)
            server.close()
            self.assertTrue(replacement.exists())
        replacement.unlink()
        self.root.rmdir()
        original.rename(self.root)
        self.assertTrue(self.path.exists())
        self.path.unlink()

    def test_parent_permissions_changed_prevent_shutdown_unlink(self):
        server = OwnedUnixListener(self.root)
        self.root.chmod(0o755)
        server.close()
        self.assertTrue(self.path.exists())
        self.root.chmod(0o700)
        self.path.unlink()

    def test_reject_insecure_directory(self):
        self.root.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            OwnedUnixListener(self.root)

    @unittest.skipUnless(hasattr(os, "fork"), "requires fork")
    def test_crashed_owner_leaves_endpoint_and_requires_explicit_cleanup(self):
        pid = os.fork()
        if pid == 0:
            try:
                server = OwnedUnixListener(self.root)
                self.assertGreaterEqual(server.socket.fileno(), 0)
                os.kill(os.getpid(), signal.SIGKILL)
            except BaseException:
                os._exit(2)
        _, status = os.waitpid(pid, 0)
        self.assertTrue(os.WIFSIGNALED(status))
        self.assertTrue(self.path.exists())
        with self.assertRaises(OSError):
            OwnedUnixListener(self.root)
        # Coordinator explicitly verifies and removes its disposable fixture.
        self.assertTrue(stat.S_ISSOCK(self.path.lstat().st_mode))
        self.path.unlink()
        with OwnedUnixListener(self.root):
            pass


if __name__ == "__main__":
    unittest.main()
