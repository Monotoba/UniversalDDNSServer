"""Real forked sender tests for optional session-bound completion exchange."""
import os
import socket
import time
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from universalddns import handoff_completion

from universalddns.handoff_completion import (
    acknowledge_verified_handoff, receive_completed_snapshot,
)
from universalddns.inventory_snapshot import publish_inventory_snapshot
from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.snapshot_handoff import HandoffSession, send_snapshot_fd
import sqlite3


@unittest.skipUnless(hasattr(os, "pidfd_open") and hasattr(socket, "SO_PEERCRED"),
                     "requires Linux pidfd and peer credentials")
class CompletionHandshakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        source = root / "source.sqlite3"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.snapshot = private / "snapshot.sqlite3"
        with sqlite3.connect(source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))
        publish_inventory_snapshot(source, self.snapshot)
        self.generation = read_consistent_snapshot(self.snapshot)["generation"]
        info = self.snapshot.stat()
        self.identity = (info.st_dev, info.st_ino)

    def scenario(self, mode, *, deadline_seconds=None):
        session = HandoffSession()
        address = "\x00uddns-ack-" + uuid.uuid4().hex
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(address)
            listener.listen(1)
            listener.settimeout(5)
            pid = os.fork()
            if pid == 0:
                listener.close()
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
                        channel.connect(address)
                        send_snapshot_fd(channel, self.snapshot,
                                         authorized_uid=os.geteuid(),
                                         session_challenge=session.challenge)
                        if mode == "crash":
                            os._exit(0)
                        if mode == "silent":
                            time.sleep(3)
                        elif mode == "oversized":
                            channel.recv(33)
                            channel.sendall(b"A" + session.challenge + b"EXTRA")
                        elif mode == "replay":
                            channel.recv(33)
                            channel.sendall(b"A" + b"0" * 32)
                        elif mode in ("fragment", "drip", "expire-after-verify"):
                            channel.recv(33)
                            frame = b"A" + session.challenge
                            for byte in frame:
                                try:
                                    channel.sendall(bytes((byte,)))
                                except BrokenPipeError:
                                    break
                                if mode == "drip":
                                    time.sleep(0.04)
                        else:
                            acknowledge_verified_handoff(
                                channel, challenge=session.challenge)
                    os._exit(0)
                except BaseException:
                    os._exit(2)
            pidfd = os.pidfd_open(pid)
            reaped = False
            try:
                with listener.accept()[0] as channel:
                    channel.settimeout(2)
                    before = len(os.listdir("/proc/self/fd"))
                    deadline = (None if deadline_seconds is None
                                else time.monotonic() + deadline_seconds)
                    if mode in ("ok", "fragment"):
                        value = receive_completed_snapshot(
                            channel, authorized_uid=os.geteuid(),
                            producer_uid=os.geteuid(), authorized_pid=pid,
                            session=session, expected_generation=self.generation,
                            expected_identity=self.identity, peer_pidfd=pidfd,
                            deadline=deadline)
                        self.assertEqual(value["generation"], self.generation)
                    else:
                        with self.assertRaisesRegex(
                                ValueError, "^snapshot unavailable$"):
                            receive_completed_snapshot(
                                channel, authorized_uid=os.geteuid(),
                                producer_uid=os.geteuid(), authorized_pid=pid,
                                session=session, expected_generation=self.generation,
                                expected_identity=self.identity, peer_pidfd=pidfd,
                                deadline=deadline)
                    self.assertTrue(session.consumed)
                    self.assertLessEqual(len(os.listdir("/proc/self/fd")), before)
                    with self.assertRaisesRegex(
                            ValueError, "^snapshot unavailable$"):
                        receive_completed_snapshot(
                            channel, authorized_uid=os.geteuid(),
                            producer_uid=os.geteuid(), authorized_pid=pid,
                            session=session, expected_generation=self.generation,
                            expected_identity=self.identity, peer_pidfd=pidfd)
            finally:
                try:
                    os.kill(pid, 9)
                except ProcessLookupError:
                    pass
                if not reaped:
                    os.waitpid(pid, 0)
                os.close(pidfd)

    def test_oversized_completion_frame_rejected(self):
        self.scenario("oversized", deadline_seconds=1.5)

    def test_repeated_oversized_and_timeout_recover(self):
        for _ in range(3):
            self.scenario("oversized", deadline_seconds=1.5)
            self.scenario("drip", deadline_seconds=0.25)
        self.scenario("ok", deadline_seconds=1.5)

    def test_fragmented_completion_within_deadline_succeeds(self):
        self.scenario("fragment", deadline_seconds=1.5)

    def test_slow_drip_cannot_extend_overall_deadline(self):
        self.scenario("drip", deadline_seconds=0.25)

    def test_deadline_expires_between_verification_and_completion(self):
        original = handoff_completion.receive_verified_snapshot

        def delayed(*args, **kwargs):
            result = original(*args, **kwargs)
            time.sleep(0.12)
            return result

        with patch.object(handoff_completion, "receive_verified_snapshot",
                          side_effect=delayed):
            self.scenario("expire-after-verify", deadline_seconds=0.08)

    def test_fresh_session_recovers_after_overall_timeout(self):
        self.scenario("drip", deadline_seconds=0.25)
        self.scenario("ok", deadline_seconds=1.5)

    def test_success_then_consumed_replay_rejected(self):
        self.scenario("ok")

    def test_incorrect_completion_echo_rejected(self):
        self.scenario("replay")

    def test_missing_completion_times_out(self):
        self.scenario("silent")

    def test_exited_sender_cannot_complete(self):
        self.scenario("crash")

    def test_new_session_recovers_after_failed_completion(self):
        self.scenario("replay")
        self.scenario("ok")


if __name__ == "__main__":
    unittest.main()
