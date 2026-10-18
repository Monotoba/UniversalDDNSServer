"""Isolated negative tests for cooperative-lock bypass and filesystem ownership."""
import multiprocessing
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from universalddns.consistent_snapshot import read_consistent_snapshot
from universalddns.inventory_snapshot import publish_inventory_snapshot
from universalddns.observer_session import observer_session
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry


def _publish_without_observer_lock(source, target):
    try:
        publish_inventory_snapshot(source, target)
    except BaseException:
        os._exit(1)
    os._exit(0)


class PublisherAuthorizationFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.live = root / "live.sqlite3"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.target = private / "inventory.sqlite3"
        with sqlite3.connect(self.live) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))

    @unittest.skipUnless(sys.platform.startswith("linux"),
                         "requires Linux fork and flock")
    def test_direct_publisher_bypasses_cooperative_observer_lock(self):
        publish_inventory_snapshot(self.live, self.target)
        original = read_consistent_snapshot(self.target)
        ctx = multiprocessing.get_context("fork")
        with observer_session(self.target):
            child = ctx.Process(target=_publish_without_observer_lock,
                                args=(str(self.live), str(self.target)))
            child.start()
            child.join(10)
            if child.is_alive():
                child.kill()
                child.join()
                self.fail("bypass fixture timed out")
            self.assertEqual(child.exitcode, 0)
            replacement = read_consistent_snapshot(self.target)
            self.assertNotEqual(original["generation"], replacement["generation"])
        # No publication acknowledgement may be inferred from the new bytes.
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            SnapshotIssuanceRegistry().validate(replacement)


@unittest.skipUnless(sys.platform.startswith("linux") and os.geteuid() == 0,
                     "requires root in disposable Linux CI fixture")
class CrossUidPublisherAuthorization(PublisherAuthorizationFixture):
    OWNER_UID = 65533
    OWNER_GID = 65533
    UNAUTHORIZED_UID = 65534
    UNAUTHORIZED_GID = 65534

    def _run_as(self, uid, gid, command):
        child = os.fork()
        if child == 0:
            try:
                os.setgroups([])
                os.setgid(gid)
                os.setuid(uid)
                command()
            except BaseException as exc:
                print("isolated authorization child failed:", repr(exc),
                      file=sys.stderr, flush=True)
                os._exit(1)
            os._exit(0)
        _, status = os.waitpid(child, 0)
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(os.WEXITSTATUS(status), 0)

    def test_unauthorized_uid_cannot_publish_or_forge_observer_lock(self):
        # Root provisions disposable ownership only; no host accounts/ACLs.
        root = self.target.parent.parent
        os.chown(root, self.OWNER_UID, self.OWNER_GID)
        os.chmod(root, 0o700)
        os.chown(self.live, self.OWNER_UID, self.OWNER_GID)
        os.chmod(self.live, 0o600)
        os.chown(self.target.parent, self.OWNER_UID, self.OWNER_GID)
        os.chmod(self.target.parent, 0o700)

        self._run_as(self.OWNER_UID, self.OWNER_GID,
                     lambda: publish_inventory_snapshot(self.live, self.target))
        before = read_consistent_snapshot(self.target)

        def forbidden():
            from universalddns.observer_session import observer_session
            attempts = (
                lambda: publish_inventory_snapshot(self.live, self.target),
                lambda: open(self.target, "wb"),
                lambda: observer_session(self.target),
            )
            for action in attempts:
                try:
                    result = action()
                except (PermissionError, ValueError, OSError):
                    continue
                else:
                    if hasattr(result, "__enter__"):
                        try:
                            with result:
                                pass
                        except (PermissionError, ValueError, OSError):
                            continue
                    raise AssertionError("unauthorized operation accepted")
            # Independently created issuance data is not the producer's token.
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                SnapshotIssuanceRegistry().validate(before)

        self._run_as(self.UNAUTHORIZED_UID, self.UNAUTHORIZED_GID, forbidden)
        after = read_consistent_snapshot(self.target)
        self.assertEqual(before["generation"], after["generation"])
