"""Boundary tests: trusted freshness must not come from snapshot metadata."""
import math
import unittest
from universalddns.snapshot_freshness import require_fresh_snapshot

GENERATION = "a" * 32


class SnapshotFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "generation": GENERATION, "created_at": 999999999999999,
            "total_records": 2, "staged_active_records": 1,
            "staged_inactive_records": 1,
        }

    def check(self, **overrides):
        values = {
            "trusted_generation": GENERATION,
            "trusted_issued_monotonic": 100.0,
            "now_monotonic": 110.0,
        }
        values.update(overrides)
        return require_fresh_snapshot(self.snapshot, **values)

    def test_current_trusted_generation_accepted(self):
        self.assertEqual(self.check()["total_records"], 2)

    def test_expired_and_future_issuance_rejected(self):
        for now in (99.9, 400.001):
            with self.subTest(now=now):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    self.check(now_monotonic=now)

    def test_wrong_or_missing_generation_rejected(self):
        for generation in ("b" * 32, "", None):
            with self.subTest(generation=generation):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    self.check(trusted_generation=generation)

    def test_invalid_clock_values_and_limits_rejected(self):
        for value in (float("nan"), math.inf, -math.inf, "100", True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    self.check(trusted_issued_monotonic=value)
        for age in (-1, 0, 301, float("nan"), True):
            with self.subTest(max_age=age):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    self.check(max_age_seconds=age)

    def test_missing_or_corrupt_aggregate_rejected(self):
        for bad in (None, True, -1, "1"):
            with self.subTest(bad=bad):
                original = self.snapshot["total_records"]
                self.snapshot["total_records"] = bad
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    self.check()
                self.snapshot["total_records"] = original
        self.snapshot["staged_active_records"] = 2
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.check()

    def test_embedded_timestamp_does_not_determine_freshness(self):
        self.snapshot["created_at"] = -999999999999
        self.assertEqual(self.check()["total_records"], 2)
        with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
            self.check(now_monotonic=9999)


if __name__ == "__main__":
    unittest.main()
