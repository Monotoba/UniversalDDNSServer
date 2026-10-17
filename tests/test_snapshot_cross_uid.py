"""Privileged Linux fixture: genuine cross-UID SCM_RIGHTS acceptance.

Run explicitly as root; ordinary unit runs skip this isolated fixture.
"""
import os
import socket
import sqlite3
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from universalddns.consistent_snapshot import read_snapshot_fd
from universalddns.inventory_snapshot import publish_inventory_snapshot
from universalddns.snapshot_handoff import receive_snapshot_fd, send_snapshot_fd

PRODUCER_UID = 65533
PRODUCER_GID = 65533
READER_UID = 65534
READER_GID = 65534


@unittest.skipUnless(sys.platform.startswith("linux") and os.geteuid() == 0,
                     "requires privileged Linux fixture")
class CrossUidSnapshotTests(unittest.TestCase):
    def test_nonprivileged_reader_receives_only_readonly_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            live = root / "live.sqlite3"
            published_dir = root / "published"
            published_dir.mkdir(mode=0o700)
            snapshot = published_dir / "inventory.sqlite3"
            with sqlite3.connect(live) as db:
                db.execute("""CREATE TABLE managed_records (
                    record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                    record_type TEXT, ttl INTEGER, values_json TEXT,
                    revision INTEGER, active INTEGER)""")
                db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                           ("one", "test", "a", "A", 300, "[]", 1, 1))
            publish_inventory_snapshot(live, snapshot)

            address = "\x00uddns-acceptance-" + uuid.uuid4().hex
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(address)
                listener.listen(1)
                listener.settimeout(8)
                child = os.fork()
                if child == 0:
                    try:
                        listener.close()
                        os.setgroups([])
                        os.setgid(READER_GID)
                        os.setuid(READER_UID)
                        for restricted in (live, snapshot):
                            try:
                                fd = os.open(restricted, os.O_RDONLY)
                            except PermissionError:
                                pass
                            else:
                                os.close(fd)
                                raise AssertionError("reader could open restricted path")
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                            client.settimeout(7)
                            client.connect(address)
                            fd = receive_snapshot_fd(
                                client, authorized_uid=0, producer_uid=0)
                            try:
                                result = read_snapshot_fd(fd, trusted_producer_uid=0)
                                assert result["total_records"] == 1
                                assert result["staged_active_records"] == 1
                                try:
                                    os.write(fd, b"no")
                                except OSError:
                                    pass
                                else:
                                    raise AssertionError("received writable descriptor")
                            finally:
                                os.close(fd)
                        os._exit(0)
                    except BaseException as exc:
                        print(f"cross-uid child failed: {exc!r}", file=sys.stderr,
                              flush=True)
                        os._exit(1)
                try:
                    with listener.accept()[0] as server:
                        server.settimeout(7)
                        send_snapshot_fd(server, snapshot,
                                         authorized_uid=READER_UID)
                finally:
                    _, status = os.waitpid(child, 0)
                self.assertTrue(os.WIFEXITED(status))
                self.assertEqual(os.WEXITSTATUS(status), 0)

    def test_nonroot_producer_to_distinct_reader_and_socket_lifecycle(self):
        """Root only provisions fixture; neither communicating process is root."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o700)
            os.chown(root, PRODUCER_UID, PRODUCER_GID)
            live = root / "live.sqlite3"
            private = root / "published"
            private.mkdir(mode=0o700)
            os.chown(private, PRODUCER_UID, PRODUCER_GID)
            # Source setup done by fixture administrator, then handed to producer.
            with sqlite3.connect(live) as db:
                db.execute("""CREATE TABLE managed_records (
                    record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                    record_type TEXT, ttl INTEGER, values_json TEXT,
                    revision INTEGER, active INTEGER)""")
                db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                           ("one", "test", "a", "A", 300, "[]", 1, 1))
            os.chown(live, PRODUCER_UID, PRODUCER_GID)
            os.chmod(live, 0o600)
            address = "\\x00uddns-nonroot-" + uuid.uuid4().hex
            producer = os.fork()
            if producer == 0:
                try:
                    os.setgroups([])
                    os.setgid(PRODUCER_GID)
                    os.setuid(PRODUCER_UID)
                    publish_inventory_snapshot(live, private / "inventory.sqlite3")
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                        listener.bind(address)
                        listener.listen(1)
                        listener.settimeout(8)
                        with listener.accept()[0] as channel:
                            channel.settimeout(7)
                            send_snapshot_fd(channel, private / "inventory.sqlite3",
                                             authorized_uid=READER_UID)
                    os._exit(0)
                except BaseException as exc:
                    print(f"nonroot producer failed: {exc!r}", file=sys.stderr, flush=True)
                    os._exit(1)
            reader = os.fork()
            if reader == 0:
                try:
                    os.setgroups([])
                    os.setgid(READER_GID)
                    os.setuid(READER_UID)
                    for path in (live, private / "inventory.sqlite3"):
                        try:
                            opened = os.open(path, os.O_RDONLY)
                        except PermissionError:
                            pass
                        else:
                            os.close(opened)
                            raise AssertionError("reader opened producer private data")
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.settimeout(7)
                        # Abstract socket may not yet be bound by producer.
                        import time
                        for attempt in range(70):
                            try:
                                client.connect(address)
                                break
                            except (ConnectionRefusedError, FileNotFoundError):
                                if attempt == 69:
                                    raise
                                time.sleep(0.05)
                        received = receive_snapshot_fd(
                            client, authorized_uid=PRODUCER_UID,
                            producer_uid=PRODUCER_UID)
                        try:
                            result = read_snapshot_fd(
                                received, trusted_producer_uid=PRODUCER_UID)
                            assert result["total_records"] == 1
                            assert result["staged_active_records"] == 1
                        finally:
                            os.close(received)
                    os._exit(0)
                except BaseException as exc:
                    print(f"nonroot reader failed: {exc!r}", file=sys.stderr, flush=True)
                    os._exit(1)
            for pid in (producer, reader):
                _, status = os.waitpid(pid, 0)
                self.assertTrue(os.WIFEXITED(status))
                self.assertEqual(os.WEXITSTATUS(status), 0)
            # Abstract socket is not a persistent filesystem path.
            self.assertFalse(any(p.name.startswith("uddns-nonroot") for p in root.iterdir()))


if __name__ == "__main__":
    unittest.main()
