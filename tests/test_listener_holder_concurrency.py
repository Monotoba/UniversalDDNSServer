"""Deterministic concurrent registry state and descriptor lifetime checks."""
import os
import threading
import unittest
from unittest.mock import patch

from universalddns.listener_holder_registry import ListenerHolderRegistry


@unittest.skipUnless(hasattr(os, "pidfd_open"), "Linux pidfd required")
class HolderRegistryConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.pid = os.getpid()
        self.source = os.pidfd_open(self.pid)
        self.addCleanup(os.close, self.source)
        self.registry = ListenerHolderRegistry()
        self.addCleanup(self.registry.close)

    def test_close_waits_for_inflight_reclaim_and_then_rejects(self):
        self.registry.register(self.pid, self.source)
        self.registry.seal()
        owned = self.registry._holders[self.pid]
        entered = threading.Event()
        release = threading.Event()
        close_done = threading.Event()
        outcomes = []

        def blocked_reclaim(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError("reclaim not released")
            os.fstat(owned)
            return False

        def reclaim_worker():
            try:
                outcomes.append(self.registry.reclaim(
                    ".", (1, 2), owner_pid=self.pid,
                    writer_exclusion_established=True))
            except BaseException as exc:
                outcomes.append(exc)

        def close_worker():
            self.registry.close()
            close_done.set()

        with patch("universalddns.listener_holder_registry.reclaim_exited_listener_socket",
                   side_effect=blocked_reclaim):
            first = threading.Thread(target=reclaim_worker)
            second = threading.Thread(target=close_worker)
            first.start()
            self.assertTrue(entered.wait(5))
            second.start()
            try:
                self.assertFalse(close_done.wait(0.05))
            finally:
                release.set()
                first.join(5)
                second.join(5)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(outcomes, [False])
        self.assertTrue(close_done.is_set())
        with self.assertRaises(OSError):
            os.fstat(owned)
        with self.assertRaisesRegex(ValueError, "holder registry closed"):
            self.registry.reclaim(".", (1, 2), owner_pid=self.pid)

    def test_seal_waits_for_inflight_registration(self):
        entered = threading.Event()
        release = threading.Event()
        seal_done = threading.Event()
        original_dup = os.dup
        failures = []

        def delayed_dup(fd):
            entered.set()
            if not release.wait(5):
                raise AssertionError("registration not released")
            return original_dup(fd)

        def register_worker():
            try:
                self.registry.register(self.pid, self.source)
            except BaseException as exc:
                failures.append(exc)

        def seal_worker():
            try:
                self.registry.seal()
            except BaseException as exc:
                failures.append(exc)
            finally:
                seal_done.set()

        with patch("universalddns.listener_holder_registry.os.dup",
                   side_effect=delayed_dup):
            first = threading.Thread(target=register_worker)
            second = threading.Thread(target=seal_worker)
            first.start()
            self.assertTrue(entered.wait(5))
            second.start()
            try:
                self.assertFalse(seal_done.wait(0.05))
            finally:
                release.set()
                first.join(5)
                second.join(5)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(self.registry._sealed)
        self.assertEqual(len(self.registry._holders), 1)
        with self.assertRaisesRegex(ValueError, "holder registry sealed"):
            self.registry.register(self.pid, self.source)


if __name__ == "__main__":
    unittest.main()
