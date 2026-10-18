"""Live pidfd gates a cross-process descriptor handoff; stale SO_PEERCRED is insufficient."""
import os
import signal
import socket
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from universalddns import verified_handoff

from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.inventory_snapshot import publish_inventory_snapshot
from universalddns.snapshot_handoff import HandoffSession, send_snapshot_fd
from universalddns.verified_handoff import receive_verified_snapshot


@unittest.skipUnless(os.name == "posix" and hasattr(os, "pidfd_open")
                     and hasattr(socket, "SO_PEERCRED"),
                     "requires Linux pidfd and SO_PEERCRED")
class PidfdHandoffLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        source = root / "source.sqlite3"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.target = private / "snapshot.sqlite3"
        with sqlite3.connect(source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))
        publish_inventory_snapshot(source, self.target)
        self.generation = read_consistent_snapshot(self.target)["generation"]
        info = self.target.stat()
        self.identity = (info.st_dev, info.st_ino)

    def exercise(self, *, exited=False, wrong_pidfd=False):
        session = HandoffSession()
        address = "\x00uddns-pidfd-" + uuid.uuid4().hex
        release_read, release_write = os.pipe()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(address)
            listener.listen(1)
            listener.settimeout(5)
            child = os.fork()
            if child == 0:
                os.close(release_write)
                listener.close()
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                        peer.connect(address)
                        send_snapshot_fd(peer, self.target,
                                         authorized_uid=os.geteuid(),
                                         session_challenge=session.challenge)
                        os.read(release_read, 1)
                    os._exit(0)
                except BaseException:
                    os._exit(2)
            os.close(release_read)
            pidfd = os.pidfd_open(child)
            other = os.pidfd_open(os.getpid()) if wrong_pidfd else None
            waited = False
            try:
                with listener.accept()[0] as channel:
                    if exited:
                        os.write(release_write, b"X")
                        _, status = os.waitpid(child, 0)
                        waited = True
                        self.assertTrue(os.WIFEXITED(status))
                        self.assertEqual(os.WEXITSTATUS(status), 0)
                    received_fds = []
                    actual_read = verified_handoff.read_snapshot_fd

                    def capture_received(fd, *, trusted_producer_uid):
                        received_fds.append(fd)
                        return actual_read(
                            fd, trusted_producer_uid=trusted_producer_uid)

                    with patch.object(verified_handoff, "read_snapshot_fd",
                                      side_effect=capture_received):
                        if exited or wrong_pidfd:
                            with self.assertRaisesRegex(
                                    ValueError, "^snapshot unavailable$"):
                                receive_verified_snapshot(
                                    channel, authorized_uid=os.geteuid(),
                                    producer_uid=os.geteuid(), authorized_pid=child,
                                    session=session, expected_generation=self.generation,
                                    expected_identity=self.identity,
                                    peer_pidfd=other if wrong_pidfd else pidfd)
                            self.assertTrue(session.consumed)
                        else:
                            result = receive_verified_snapshot(
                                channel, authorized_uid=os.geteuid(),
                                producer_uid=os.geteuid(), authorized_pid=child,
                                session=session, expected_generation=self.generation,
                                expected_identity=self.identity, peer_pidfd=pidfd)
                            self.assertEqual(result["generation"], self.generation)
                    # A rejected pidfd is checked before receiving SCM_RIGHTS.
                    self.assertEqual(len(received_fds), 0 if (
                        exited or wrong_pidfd) else 1)
                    for received_fd in received_fds:
                        with self.assertRaises(OSError):
                            os.fstat(received_fd)
            finally:
                if not waited:
                    try:
                        os.write(release_write, b"X")
                    except BrokenPipeError:
                        pass
                    _, status = os.waitpid(child, 0)
                    self.assertTrue(os.WIFEXITED(status))
                os.close(release_write)
                os.close(pidfd)
                if other is not None:
                    os.close(other)

    def test_sender_killed_during_pinned_verification_fails_and_recovers(self):
        """Synchronize termination inside the actual descriptor-read stage."""
        session = HandoffSession()
        address = "\x00uddns-mid-read-" + uuid.uuid4().hex
        release_read, release_write = os.pipe()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(address)
            listener.listen(1)
            listener.settimeout(5)
            child = os.fork()
            if child == 0:
                os.close(release_write)
                listener.close()
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                        peer.connect(address)
                        send_snapshot_fd(
                            peer, self.target, authorized_uid=os.geteuid(),
                            session_challenge=session.challenge)
                        os.read(release_read, 1)
                    os._exit(0)
                except BaseException:
                    os._exit(2)
            os.close(release_read)
            pidfd = os.pidfd_open(child)
            reaped = False
            try:
                with listener.accept()[0] as channel:
                    received_fds = []
                    actual_read = verified_handoff.read_snapshot_fd
                    invoked = []

                    def kill_during_read(fd, *, trusted_producer_uid):
                        received_fds.append(fd)
                        result = actual_read(
                            fd, trusted_producer_uid=trusted_producer_uid)
                        os.kill(child, signal.SIGKILL)
                        _, status = os.waitpid(child, 0)
                        invoked.append(status)
                        return result

                    with patch.object(verified_handoff, "read_snapshot_fd",
                                      side_effect=kill_during_read):
                        with self.assertRaisesRegex(
                                ValueError, "^snapshot unavailable$"):
                            receive_verified_snapshot(
                                channel, authorized_uid=os.geteuid(),
                                producer_uid=os.geteuid(), authorized_pid=child,
                                session=session, expected_generation=self.generation,
                                expected_identity=self.identity, peer_pidfd=pidfd)
                    reaped = True
                    self.assertEqual(len(invoked), 1)
                    self.assertTrue(os.WIFSIGNALED(invoked[0]))
                    self.assertEqual(os.WTERMSIG(invoked[0]), signal.SIGKILL)
                    self.assertTrue(session.consumed)
                    # Verify the actual received SCM_RIGHTS descriptor closed.
                    self.assertEqual(len(received_fds), 1)
                    with self.assertRaises(OSError):
                        os.fstat(received_fds[0])
            finally:
                if not reaped:
                    try:
                        os.kill(child, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    os.waitpid(child, 0)
                os.close(release_write)
                os.close(pidfd)
        # A new socket, PID and session must remain usable after the failure.
        self.exercise()

    def test_live_sender_accepted_with_pinned_pidfd(self):
        self.exercise()

    def test_exited_sender_rejected_despite_queued_rights(self):
        self.exercise(exited=True)

    def test_unrelated_live_pidfd_rejected(self):
        self.exercise(wrong_pidfd=True)


if __name__ == "__main__":
    unittest.main()
