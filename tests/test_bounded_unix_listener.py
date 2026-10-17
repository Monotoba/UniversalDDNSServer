"""Bound accepted Unix sockets and recover after stalled or exited peers."""
import os
import socket
import tempfile
import unittest
from pathlib import Path

from universalddns.bounded_unix_listener import BoundedUnixListener


class BoundedListenerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.address = str(Path(self.tmp.name) / "ipc.sock")
        raw = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        raw.bind(self.address)
        raw.listen(8)
        self.server = BoundedUnixListener(raw, max_active=2)
        self.addCleanup(self.server.close)
        self.clients = []
        self.addCleanup(self._close_clients)

    def _close_clients(self):
        for client in self.clients:
            client.close()

    def connect(self):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(2)
        client.connect(self.address)
        self.clients.append(client)
        return client

    def test_bounded_accept_rejection_closes_excess_fd_and_recovers(self):
        a = self.connect()
        b = self.connect()
        c = self.connect()
        first = self.server.accept()
        second = self.server.accept()
        self.assertEqual(self.server.active_count, 2)
        before = len(os.listdir("/proc/self/fd"))
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.server.accept()
        self.assertEqual(self.server.active_count, 2)
        self.assertEqual(len(os.listdir("/proc/self/fd")), before)
        self.server.release(first)
        self.assertEqual(self.server.active_count, 1)
        replacement = self.connect()
        admitted = self.server.accept()
        self.assertEqual(self.server.active_count, 2)
        admitted.sendall(b"R")
        self.assertEqual(replacement.recv(1), b"R")
        self.server.release(second)
        self.server.release(admitted)
        self.assertEqual(self.server.active_count, 0)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.server.release(first)
        a.close()
        b.close()
        c.close()

    def test_stalled_client_timeout_and_slot_release(self):
        self.connect()
        with self.server.admitted(timeout=0.05) as channel:
            with self.assertRaises(socket.timeout):
                channel.recv(1)
            self.assertEqual(self.server.active_count, 1)
        self.assertEqual(self.server.active_count, 0)
        good = self.connect()
        with self.server.admitted() as channel:
            channel.sendall(b"ok")
            self.assertEqual(good.recv(2), b"ok")
        self.assertEqual(self.server.active_count, 0)

    @unittest.skipUnless(hasattr(os, "fork"), "requires fork")
    def test_terminated_client_releases_slot_and_new_client_succeeds(self):
        pid = os.fork()
        if pid == 0:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                    peer.connect(self.address)
                    peer.sendall(b"E")
                os._exit(0)
            except BaseException:
                os._exit(3)
        _, status = os.waitpid(pid, 0)
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)
        with self.server.admitted() as channel:
            self.assertEqual(channel.recv(1), b"E")
            self.assertEqual(channel.recv(1), b"")
        self.assertEqual(self.server.active_count, 0)
        next_client = self.connect()
        with self.server.admitted() as channel:
            channel.sendall(b"N")
            self.assertEqual(next_client.recv(1), b"N")

    def test_close_releases_all_accepted_descriptors(self):
        self.connect()
        self.connect()
        first = self.server.accept()
        second = self.server.accept()
        self.assertEqual(self.server.active_count, 2)
        self.server.close()
        self.assertEqual(self.server.active_count, 0)
        self.assertEqual(first.fileno(), -1)
        self.assertEqual(second.fileno(), -1)


if __name__ == "__main__":
    unittest.main()
