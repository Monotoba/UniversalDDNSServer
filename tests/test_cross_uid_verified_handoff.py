"""Privileged disposable cross-UID SCM_RIGHTS handoff.

The observer cannot traverse the publisher's 0700 directory but receives
only a verified read-only FD over an authenticated Unix socket.
"""
import os
import socket
import sqlite3
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.inventory_snapshot import publish_inventory_snapshot
from universalddns.snapshot_handoff import HandoffSession, send_snapshot_fd
from universalddns.verified_handoff import receive_verified_snapshot


@unittest.skipUnless(sys.platform.startswith("linux") and os.geteuid() == 0,
                     "requires privileged disposable Linux test runner")
class CrossUidReadOnlyHandoff(unittest.TestCase):
    def test_distinct_observer_receives_verified_fd_without_write_authority(self):
        publisher_uid, publisher_gid = 65533, 65533
        observer_uid, observer_gid = 65534, 65534
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.sqlite3"
            private = root / "private"
            private.mkdir(mode=0o700)
            target = private / "snapshot.sqlite3"
            with sqlite3.connect(source) as db:
                db.execute("""CREATE TABLE managed_records (
                    record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                    record_type TEXT, ttl INTEGER, values_json TEXT,
                    revision INTEGER, active INTEGER)""")
                db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                           ("one", "test", "a", "A", 300, "[]", 1, 1))
            for path in (root, private, source):
                os.chown(path, publisher_uid, publisher_gid)
                path.chmod(0o600 if path == source else 0o700)
            publisher = os.fork()
            if publisher == 0:
                try:
                    os.setgroups([])
                    os.setgid(publisher_gid)
                    os.setuid(publisher_uid)
                    publish_inventory_snapshot(source, target)
                    os._exit(0)
                except BaseException:
                    os._exit(2)
            _, status = os.waitpid(publisher, 0)
            self.assertTrue(os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0)
            expected = read_consistent_snapshot(
                target, trusted_producer_uid=publisher_uid)
            identity = target.stat()
            session = HandoffSession()
            address = "\x00uddns-privsep-" + uuid.uuid4().hex
            # The observer binds the server socket *after dropping privilege*.
            ready_r, ready_w = os.pipe()
            observer = os.fork()
            if observer == 0:
                os.close(ready_r)
                try:
                    os.setgroups([])
                    os.setgid(observer_gid)
                    os.setuid(observer_uid)
                    for flags in (os.O_RDONLY, os.O_WRONLY):
                        try:
                            fd = os.open(target, flags)
                        except PermissionError:
                            pass
                        else:
                            os.close(fd)
                            raise AssertionError("observer accessed publisher pathname")
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                        listener.bind(address)
                        listener.listen(1)
                        listener.settimeout(5)
                        os.write(ready_w, b"R")
                        os.close(ready_w)
                        with listener.accept()[0] as connection:
                            connection.settimeout(5)
                            result = receive_verified_snapshot(
                                connection, authorized_uid=publisher_uid,
                                producer_uid=publisher_uid, session=session,
                                expected_generation=expected["generation"],
                                expected_identity=(identity.st_dev, identity.st_ino))
                            assert result["total_records"] == 1
                    os._exit(0)
                except BaseException:
                    os._exit(3)
            os.close(ready_w)
            try:
                self.assertEqual(os.read(ready_r, 1), b"R")
                sender = os.fork()
                if sender == 0:
                    try:
                        os.setgroups([])
                        os.setgid(publisher_gid)
                        os.setuid(publisher_uid)
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
                            channel.settimeout(5)
                            channel.connect(address)
                            send_snapshot_fd(
                                channel, target, authorized_uid=observer_uid,
                                session_challenge=session.challenge)
                        os._exit(0)
                    except BaseException:
                        os._exit(4)
                _, sender_status = os.waitpid(sender, 0)
                self.assertTrue(os.WIFEXITED(sender_status))
                self.assertEqual(os.WEXITSTATUS(sender_status), 0)
                _, observer_status = os.waitpid(observer, 0)
                self.assertTrue(os.WIFEXITED(observer_status))
                self.assertEqual(os.WEXITSTATUS(observer_status), 0)
            finally:
                os.close(ready_r)
                try:
                    os.kill(observer, 9)
                except ProcessLookupError:
                    pass


if __name__ == "__main__":
    unittest.main()
