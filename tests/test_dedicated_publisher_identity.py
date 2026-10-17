"""Disposable Linux permission boundaries for dedicated snapshot publisher UID.

Does not create accounts, use setfacl, or modify any deployed directory.
"""
import os
import sqlite3
import stat
import sys
import tempfile
import unittest
from pathlib import Path

from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.inventory_snapshot import publish_inventory_snapshot


@unittest.skipUnless(sys.platform.startswith("linux") and os.geteuid() == 0,
                     "cross-UID privilege separation requires root Linux fixture")
class DedicatedPublisherIdentityTests(unittest.TestCase):
    PUBLISHER_UID = 65533
    PUBLISHER_GID = 65533
    OBSERVER_UID = 65534
    OBSERVER_GID = 65534

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "live.sqlite3"
        self.private = root / "publisher-private"
        self.private.mkdir(mode=0o700)
        self.destination = self.private / "snapshot.sqlite3"
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))
        for item in (root, self.private):
            os.chown(item, self.PUBLISHER_UID, self.PUBLISHER_GID)
            item.chmod(0o700)
        os.chown(self.source, self.PUBLISHER_UID, self.PUBLISHER_GID)
        self.source.chmod(0o600)

    def run_as(self, uid, gid, task):
        pid = os.fork()
        if pid == 0:
            try:
                os.setgroups([])
                os.setgid(gid)
                os.setuid(uid)
                task()
            except BaseException:
                os._exit(1)
            os._exit(0)
        _, status = os.waitpid(pid, 0)
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)

    def publish_as_owner(self):
        self.run_as(self.PUBLISHER_UID, self.PUBLISHER_GID,
                    lambda: publish_inventory_snapshot(
                        self.source, self.destination))

    def test_dedicated_owner_publishes_observer_cannot_mutate_or_reopen(self):
        self.publish_as_owner()
        first = read_consistent_snapshot(
            self.destination, trusted_producer_uid=self.PUBLISHER_UID)

        def observer_attempts():
            operations = (
                lambda: publish_inventory_snapshot(self.source, self.destination),
                lambda: os.open(self.destination, os.O_WRONLY),
                lambda: os.replace(self.destination, self.private / "substitute"),
                lambda: os.open(self.destination, os.O_RDONLY),
                lambda: os.open(self.private, os.O_RDONLY | os.O_DIRECTORY),
            )
            for action in operations:
                try:
                    fd = action()
                except (OSError, ValueError):
                    continue
                if isinstance(fd, int):
                    os.close(fd)
                raise AssertionError("observer bypassed publisher-only directory")
        self.run_as(self.OBSERVER_UID, self.OBSERVER_GID, observer_attempts)
        after = read_consistent_snapshot(
            self.destination, trusted_producer_uid=self.PUBLISHER_UID)
        self.assertEqual(first["generation"], after["generation"])
        self.publish_as_owner()
        second = read_consistent_snapshot(
            self.destination, trusted_producer_uid=self.PUBLISHER_UID)
        self.assertNotEqual(first["generation"], second["generation"])

    def test_permission_boundary_persists_after_publisher_crash(self):
        self.publish_as_owner()
        # A killed owner cannot transfer write authority to the observer.
        pid = os.fork()
        if pid == 0:
            os.setgroups([])
            os.setgid(self.PUBLISHER_GID)
            os.setuid(self.PUBLISHER_UID)
            os.kill(os.getpid(), 9)
        _, status = os.waitpid(pid, 0)
        self.assertTrue(os.WIFSIGNALED(status))
        def observer_denied():
            try:
                fd = os.open(self.destination, os.O_WRONLY)
            except PermissionError:
                return
            os.close(fd)
            raise AssertionError("observer gained write permission after crash")
        self.run_as(self.OBSERVER_UID, self.OBSERVER_GID, observer_denied)
        self.assertEqual(stat.S_IMODE(self.private.stat().st_mode), 0o700)
        self.publish_as_owner()


if __name__ == "__main__":
    unittest.main()
