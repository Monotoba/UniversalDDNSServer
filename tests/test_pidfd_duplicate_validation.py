"""Deterministic duplicate-before-validation registry regression tests."""
import os
import unittest
from unittest.mock import patch

from universalddns.listener_holder_registry import ListenerHolderRegistry


@unittest.skipUnless(hasattr(os, "pidfd_open"), "Linux pidfd required")
class PidfdDuplicateValidationTests(unittest.TestCase):
    def setUp(self):
        self.pid = os.getpid()
        self.source = os.pidfd_open(self.pid)
        self.addCleanup(os.close, self.source)
        self.registry = ListenerHolderRegistry()
        self.addCleanup(self.registry.close)

    def test_original_number_reassigned_after_duplicate_is_safe(self):
        original_dup = os.dup
        def swap_after_dup(fd):
            owned = original_dup(fd)
            with open(os.devnull, "rb") as other:
                os.dup2(other.fileno(), fd)
            return owned
        with patch("universalddns.listener_holder_registry.os.dup",
                   side_effect=swap_after_dup):
            self.registry.register(self.pid, self.source)
        owned = self.registry._holders[self.pid]
        with open(f"/proc/self/fdinfo/{owned}", encoding="ascii") as record:
            self.assertIn(f"Pid:\t{self.pid}", record.read())
        self.assertFalse(os.get_inheritable(owned))
        self.assertEqual(len(self.registry._holders), 1)

    def test_invalid_duplicated_descriptor_rejected_without_leak(self):
        source = self.source
        original_dup = os.dup
        allocated = []
        def substitute(fd):
            with open(os.devnull, "rb") as other:
                owned = original_dup(other.fileno())
            allocated.append(owned)
            return owned
        with patch("universalddns.listener_holder_registry.os.dup",
                   side_effect=substitute):
            with self.assertRaisesRegex(ValueError, "invalid holder registration"):
                self.registry.register(self.pid, source)
        self.assertEqual(self.registry._holders, {})
        self.assertEqual(len(allocated), 1)
        with self.assertRaises(OSError):
            os.fstat(allocated[0])
        self.registry.register(self.pid, source)
        self.assertEqual(len(self.registry._holders), 1)

    def test_duplicating_invalid_fd_fails_closed(self):
        os.close(self.source)
        with self.assertRaisesRegex(ValueError, "invalid holder registration"):
            self.registry.register(self.pid, self.source)
        self.assertFalse(self.registry._holders)
        # Reestablish the fixture's caller-owned fd for setUp cleanup.
        fresh = os.pidfd_open(self.pid)
        os.dup2(fresh, self.source)
        if fresh != self.source:
            os.close(fresh)


if __name__ == "__main__":
    unittest.main()
