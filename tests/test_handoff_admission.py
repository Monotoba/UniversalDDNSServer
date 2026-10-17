"""Deterministic process-local admission and repeated-rejection checks."""
import threading
import unittest

from universalddns.handoff_admission import HandoffAdmission


class AdmissionTests(unittest.TestCase):
    def test_competing_threads_fail_immediately_then_recover(self):
        guard = HandoffAdmission()
        acquired = threading.Event()
        release = threading.Event()
        outcomes = []

        def holder():
            with guard.admit():
                acquired.set()
                release.wait(3)

        thread = threading.Thread(target=holder)
        thread.start()
        try:
            self.assertTrue(acquired.wait(3))
            for _ in range(25):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    with guard.admit():
                        self.fail("concurrent caller entered")
                outcomes.append("rejected")
            self.assertEqual(len(outcomes), 25)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        with guard.admit():
            pass

    def test_exception_releases_admission(self):
        guard = HandoffAdmission()
        for _ in range(20):
            with self.assertRaisesRegex(RuntimeError, "aborted"):
                with guard.admit():
                    raise RuntimeError("aborted")
        with guard.admit():
            pass


if __name__ == "__main__":
    unittest.main()
