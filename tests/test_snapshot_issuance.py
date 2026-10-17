"""Isolated issuer trust, replacement and process-boundary tests."""
import os
import unittest
from unittest.mock import patch

from universalddns.snapshot_issuance import SnapshotIssuanceRegistry

GEN1 = "a" * 32
GEN2 = "b" * 32


def snapshot(generation):
    return {"generation": generation, "created_at": 0, "total_records": 1,
            "staged_active_records": 1, "staged_inactive_records": 0}


class SnapshotIssuanceTests(unittest.TestCase):
    def test_matching_generation_and_expiry(self):
        registry = SnapshotIssuanceRegistry()
        registry.issue(GEN1, observed_monotonic=100.0)
        self.assertEqual(registry.validate(snapshot(GEN1), now_monotonic=110.0)["total_records"], 1)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            registry.validate(snapshot(GEN1), now_monotonic=401.0)

    def test_replace_revokes_old_generation(self):
        registry = SnapshotIssuanceRegistry()
        registry.issue(GEN1, observed_monotonic=100.0)
        registry.issue(GEN2, observed_monotonic=110.0)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            registry.validate(snapshot(GEN1), now_monotonic=111.0)
        self.assertEqual(registry.validate(snapshot(GEN2), now_monotonic=111.0)["total_records"], 1)

    def test_new_registry_and_invalidated_state_fail_closed(self):
        registry = SnapshotIssuanceRegistry()
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            registry.validate(snapshot(GEN1), now_monotonic=101.0)
        registry.issue(GEN1, observed_monotonic=100.0)
        restarted = SnapshotIssuanceRegistry()
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            restarted.validate(snapshot(GEN1), now_monotonic=101.0)
        registry.invalidate()
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            registry.validate(snapshot(GEN1), now_monotonic=101.0)

    def test_rewound_clock_and_invalid_issuance_rejected(self):
        registry = SnapshotIssuanceRegistry()
        registry.issue(GEN1, observed_monotonic=100.0)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            registry.issue(GEN2, observed_monotonic=99.0)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            registry.issue("garbage", observed_monotonic=101.0)
        self.assertEqual(registry.validate(snapshot(GEN1), now_monotonic=102.0)["total_records"], 1)

    def test_pid_change_invalidates_inherited_trust(self):
        registry = SnapshotIssuanceRegistry()
        registry.issue(GEN1, observed_monotonic=100.0)
        with patch("universalddns.snapshot_issuance.os.getpid", return_value=os.getpid() + 1):
            with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                registry.validate(snapshot(GEN1), now_monotonic=101.0)


if __name__ == "__main__":
    unittest.main()
