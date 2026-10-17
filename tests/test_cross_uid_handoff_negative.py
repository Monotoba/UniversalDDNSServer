"""Privileged cross-UID rejection tests for isolated Unix descriptor handoff."""
import os
import socket
import sqlite3
import sys
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


@unittest.skipUnless(sys.platform.startswith("linux") and os.geteuid() == 0,
                     "requires privileged disposable Linux CI")
class CrossUidNegativeHandoffTests(unittest.TestCase):
    PUBLISHER = 65533
    OBSERVER = 65534
    IMPOSTOR = 65532

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "live.sqlite3"
        self.private = root / "private"
        self.private.mkdir(mode=0o700)
        self.target = self.private / "snapshot.sqlite3"
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))
        for path in (root, self.private, self.source):
            os.chown(path, self.PUBLISHER, self.PUBLISHER)
            path.chmod(0o600 if path == self.source else 0o700)
        self._fork_owner(lambda: publish_inventory_snapshot(
            self.source, self.target))
        self.expected = read_consistent_snapshot(
            self.target, trusted_producer_uid=self.PUBLISHER)
        info = self.target.stat()
        self.identity = (info.st_dev, info.st_ino)

    def _drop(self, uid):
        os.setgroups([])
        os.setgid(uid)
        os.setuid(uid)

    def _fork_owner(self, action):
        pid = os.fork()
        if pid == 0:
            try:
                self._drop(self.PUBLISHER)
                action()
                os._exit(0)
            except BaseException:
                os._exit(90)
        _, status = os.waitpid(pid, 0)
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)

    def _case(self, mode):
        session = HandoffSession()
        address = "\x00uddns-negative-" + uuid.uuid4().hex
        read_ready, write_ready = os.pipe()
        pid_read, pid_write = os.pipe()
        observer = os.fork()
        if observer == 0:
            os.close(read_ready)
            os.close(pid_write)
            try:
                self._drop(self.OBSERVER)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                    listener.bind(address)
                    listener.listen(1)
                    listener.settimeout(4)
                    os.write(write_ready, b"R")
                    os.close(write_ready)
                    with listener.accept()[0] as peer:
                        peer.settimeout(2)
                        expected_pid = int(os.read(pid_read, 32).decode("ascii"))
                        os.close(pid_read)
                        if mode == "wrong-pid":
                            expected_pid += 100000
                        try:
                            receive_verified_snapshot(
                                peer, authorized_uid=self.PUBLISHER,
                                producer_uid=self.PUBLISHER, session=session,
                                authorized_pid=expected_pid,
                                expected_generation=self.expected["generation"],
                                expected_identity=self.identity)
                        except ValueError:
                            if not session.consumed:
                                os._exit(91)
                            os._exit(0)
                        os._exit(92)
            except BaseException:
                os._exit(93)
        os.close(write_ready)
        os.close(pid_read)
        sender = None
        try:
            self.assertEqual(os.read(read_ready, 1), b"R")
            sender = os.fork()
            if sender == 0:
                try:
                    self._drop(self.IMPOSTOR if mode == "wrong-uid" else self.PUBLISHER)
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                        peer.settimeout(2)
                        peer.connect(address)
                        if mode == "crash":
                            os._exit(86)
                        if mode == "wrong-uid":
                            peer.sendall(b"X")
                        else:
                            target = (self.private / "alternate.sqlite3"
                                      if mode == "wrong-inode" else self.target)
                            challenge = (b"0" * 32 if mode == "wrong-challenge"
                                         else session.challenge)
                            send_snapshot_fd(
                                peer, target, authorized_uid=self.OBSERVER,
                                session_challenge=challenge)
                    os._exit(0)
                except BaseException:
                    os._exit(94)
            os.write(pid_write, str(sender).encode("ascii"))
            os.close(pid_write)
            _, status = os.waitpid(sender, 0)
            sender = None
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 86 if mode == "crash" else 0)
            _, status = os.waitpid(observer, 0)
            observer = None
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)
        finally:
            os.close(read_ready)
            for pid in (sender, observer):
                if pid is not None:
                    try:
                        os.kill(pid, 9)
                    except ProcessLookupError:
                        pass
                    os.waitpid(pid, 0)


    def _successful_recovery(self):
        """Fresh cross-UID session succeeds after rejected transfers."""
        session = HandoffSession()
        address = "\x00uddns-recovery-" + uuid.uuid4().hex
        ready_r, ready_w = os.pipe()
        pid_read, pid_write = os.pipe()
        observer = os.fork()
        if observer == 0:
            os.close(ready_r)
            os.close(pid_write)
            try:
                self._drop(self.OBSERVER)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                    listener.bind(address)
                    listener.listen(1)
                    listener.settimeout(4)
                    os.write(ready_w, b"R")
                    os.close(ready_w)
                    with listener.accept()[0] as peer:
                        expected_pid = int(os.read(pid_read, 32).decode("ascii"))
                        os.close(pid_read)
                        received = []
                        actual_read = verified_handoff.read_snapshot_fd

                        def capture(fd, *, trusted_producer_uid):
                            received.append(fd)
                            return actual_read(
                                fd, trusted_producer_uid=trusted_producer_uid)

                        with patch.object(verified_handoff, "read_snapshot_fd",
                                          side_effect=capture):
                            verified = receive_verified_snapshot(
                                peer, authorized_uid=self.PUBLISHER,
                                producer_uid=self.PUBLISHER, session=session,
                                authorized_pid=expected_pid,
                                expected_generation=self.expected["generation"],
                                expected_identity=self.identity)
                        if (verified["generation"] != self.expected["generation"]
                                or not session.consumed or len(received) != 1):
                            os._exit(80)
                        try:
                            os.fstat(received[0])
                        except OSError:
                            pass
                        else:
                            os._exit(80)
                        try:
                            receive_verified_snapshot(
                                peer, authorized_uid=self.PUBLISHER,
                                producer_uid=self.PUBLISHER, session=session,
                                authorized_pid=expected_pid,
                                expected_generation=self.expected["generation"])
                        except ValueError:
                            os._exit(0)
                        os._exit(81)
            except BaseException:
                os._exit(82)
        os.close(ready_w)
        os.close(pid_read)
        sender = None
        try:
            self.assertEqual(os.read(ready_r, 1), b"R")
            sender = os.fork()
            if sender == 0:
                try:
                    self._drop(self.PUBLISHER)
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                        peer.settimeout(3)
                        peer.connect(address)
                        send_snapshot_fd(
                            peer, self.target, authorized_uid=self.OBSERVER,
                            session_challenge=session.challenge)
                    os._exit(0)
                except BaseException:
                    os._exit(83)
            os.write(pid_write, str(sender).encode("ascii"))
            os.close(pid_write)
            _, status = os.waitpid(sender, 0)
            sender = None
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)
            _, status = os.waitpid(observer, 0)
            observer = None
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)
        finally:
            os.close(ready_r)
            for pid in (sender, observer):
                if pid is not None:
                    try:
                        os.kill(pid, 9)
                    except ProcessLookupError:
                        pass
                    os.waitpid(pid, 0)

    def test_generation_rollover_requires_fresh_authorized_expectations(self):
        """New bytes cannot be trusted using the preceding generation/inode."""
        old_generation = self.expected["generation"]
        old_identity = self.identity
        self._fork_owner(lambda: publish_inventory_snapshot(
            self.source, self.target))
        current = read_consistent_snapshot(
            self.target, trusted_producer_uid=self.PUBLISHER)
        details = self.target.stat()
        current_identity = (details.st_dev, details.st_ino)
        self.assertNotEqual(old_generation, current["generation"])
        self.assertNotEqual(old_identity, current_identity)

        # A legitimate sender's current descriptor is not sufficient when
        # the observer still trusts the previous publication.
        self._case("normal")

        # Matching generation alone is insufficient when inode continuity
        # belongs to the preceding authorized publication.
        self.expected = current
        self._case("normal")

        # Fresh independently observed generation AND inode permit a new
        # single-use authenticated cross-UID session.
        self.identity = current_identity
        self._successful_recovery()

    def test_repeated_rejections_crashes_and_fresh_session_recovery(self):
        """Repeated rejected cross-UID transfers permit a fresh verified session."""
        for mode in ("wrong-uid", "wrong-challenge", "crash") * 3:
            self._case(mode)
        self._successful_recovery()

    def test_wrong_exact_peer_pid_rejected(self):
        self._case("wrong-pid")

    def test_wrong_uid_rejected(self):
        self._case("wrong-uid")

    def test_wrong_session_challenge_rejected(self):
        self._case("wrong-challenge")

    def test_wrong_snapshot_inode_rejected(self):
        self._fork_owner(lambda: publish_inventory_snapshot(
            self.source, self.private / "alternate.sqlite3"))
        self._case("wrong-inode")

    def test_publisher_disconnect_before_transfer_rejected(self):
        self._case("crash")


if __name__ == "__main__":
    unittest.main()
