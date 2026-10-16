"""Execute lifecycle cleanup with a mocked sudo command, never systemd."""
import os
from pathlib import Path
import subprocess
import unittest

SCRIPT = (Path(__file__).resolve().parents[1] / "tests" / "deployment"
          / "test-operator-systemd-lifecycle.sh")


class BrokerCleanupExecutionTests(unittest.TestCase):
    @staticmethod
    def execute(fail="", active=False, original_status=0):
        source = SCRIPT.read_text(encoding="utf-8")
        function = source.split("cleanup() {", 1)[1].split("\ntrap cleanup EXIT", 1)[0]
        # Only execute the extracted function; never execute the provisioning body.
        script = """#!/usr/bin/env bash
set -Eeuo pipefail
socket_unit=/not-a-real-broker-test-unit.socket
service_unit=/not-a-real-broker-test-unit.service
sudo() {
  case "$1 $2" in
    "systemctl stop") [[ "$FAIL_AT" != stop ]] ;;
    "systemctl is-active") [[ "$ACTIVE" == yes ]] ;;
    "rm -f") [[ "$FAIL_AT" != remove ]] ;;
    "systemctl daemon-reload") [[ "$FAIL_AT" != reload ]] ;;
    *) return 99 ;;
  esac
}
cleanup() {""" + function + "\n" + f"(exit {original_status})\ncleanup\n"
        env = dict(os.environ, FAIL_AT=fail, ACTIVE="yes" if active else "no")
        return subprocess.run(["bash", "-c", script], capture_output=True,
                              text=True, timeout=5, env=env, check=False)

    def test_successful_cleanup_exits_success(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_stop_preserves_units_and_fails(self):
        result = self.execute(fail="stop")
        self.assertEqual(result.returncode, 1)
        self.assertIn("preserving test unit files", result.stderr)

    def test_still_active_broker_preserves_units_and_fails(self):
        result = self.execute(active=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("broker still active", result.stderr)

    def test_failed_remove_never_reports_success(self):
        result = self.execute(fail="remove")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unable to remove", result.stderr)

    def test_failed_reload_never_reports_success(self):
        result = self.execute(fail="reload")
        self.assertEqual(result.returncode, 1)
        self.assertIn("reload after cleanup failed", result.stderr)

    def test_preserves_original_nonzero_exit_status(self):
        result = self.execute(original_status=23)
        self.assertEqual(result.returncode, 23, result.stderr)


if __name__ == "__main__":
    unittest.main()
