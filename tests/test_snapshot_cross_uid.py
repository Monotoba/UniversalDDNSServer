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


if __name__ == "__main__":
    unittest.main()
