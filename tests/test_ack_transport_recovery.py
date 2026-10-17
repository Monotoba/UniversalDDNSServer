"""Adversarial isolated pipe transport and child-process cleanup acceptance."""
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.ack_frame import FRAME_BYTES, encode_ack
from universalddns.authorized_observer import publish_with_authorized_child
from universalddns.snapshot_issuance import SnapshotIssuanceRegistry


@unittest.skipUnless(os.name == "posix" and hasattr(os, "fork"),
                     "requires POSIX fork and raw pipe framing")
class AcknowledgementRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "live.sqlite3"
        private = root / "private"
        private.mkdir(mode=0o700)
        self.target = private / "snapshot.sqlite3"
        self.registry = SnapshotIssuanceRegistry()
        with sqlite3.connect(self.source) as db:
            db.execute("""CREATE TABLE managed_records (
                record_id TEXT PRIMARY KEY, zone TEXT, name TEXT,
                record_type TEXT, ttl INTEGER, values_json TEXT,
                revision INTEGER, active INTEGER)""")
            db.execute("INSERT INTO managed_records VALUES (?,?,?,?,?,?,?,?)",
                       ("one", "test", "a", "A", 300, "[]", 1, 1))

    def test_truncated_header_body_oversize_stall_and_duplicate_rejected(self):
        from universalddns import authorized_observer

        for case in ("partial-header", "partial-body", "oversized",
                     "stall", "duplicate"):
            with self.subTest(case=case):
                def malicious(source, destination, connection, nonce):
                    fd = connection.fileno()
                    frame = encode_ack(nonce, "a" * 32)
                    if case == "partial-header":
                        os.write(fd, b"\\x00\\x00")
                    elif case == "partial-body":
                        os.write(fd, FRAME_BYTES.to_bytes(4, "big") + frame[:3])
                    elif case == "oversized":
                        os.write(fd, (FRAME_BYTES + 1).to_bytes(4, "big"))
                    elif case == "duplicate":
                        connection.send_bytes(frame)
                        connection.send_bytes(frame)
                    else:
                        pass
                    if case != "duplicate" and case != "oversized":
                        time.sleep(2)
                    connection.close()

                with patch.object(authorized_observer, "_publisher_child",
                                  side_effect=malicious):
                    started = time.monotonic()
                    with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                        publish_with_authorized_child(
                            self.source, self.target, self.registry,
                            timeout_seconds=0.2)
                    self.assertLess(time.monotonic() - started, 1.8)
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    self.registry.validate({"generation": "a" * 32})

    def test_recovery_after_killed_partial_writer(self):
        from universalddns import authorized_observer

        def partial(source, destination, connection, nonce):
            os.write(connection.fileno(), FRAME_BYTES.to_bytes(4, "big") + b"x")
            time.sleep(2)

        with patch.object(authorized_observer, "_publisher_child",
                          side_effect=partial):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                publish_with_authorized_child(
                    self.source, self.target, self.registry,
                    timeout_seconds=0.2)
        result = publish_with_authorized_child(
            self.source, self.target, self.registry)
        self.assertEqual(result["total_records"], 1)


if __name__ == "__main__":
    unittest.main()
