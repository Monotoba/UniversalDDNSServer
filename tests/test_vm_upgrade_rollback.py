"""Isolated fault-injection tests for VM upgrade rollback."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "tests/deployment/update-vm.sh"


def rollback_function():
    source = UPDATER.read_text()
    start = source.index("rollback() {")
    # The rollback function ends before the preflight backup section.
    # Do not include updater commands executed before trap installation.
    end = source.index(
        "\n}\n\n# Complete non-destructive preflight backups",
        start,
    )
    return source[start:end + 2]


class RollbackFaultInjectionTests(unittest.TestCase):

    def run_rollback(self, *, missing_worker_unit=False, fail_install=False, fail_operation=None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            backup = root / "backup"
            backup.mkdir()

            (backup / "state.sqlite3").write_bytes(b"test-database")
            (backup / "universalddns-api.service").write_text("old-api")

            if not missing_worker_unit:
                (backup / "universalddns-worker.service").write_text(
                    "old-worker"
                )

            mock = root / "sudo"
            mock.write_text(
                """#!/bin/sh
printf '%s\\n' "$*" >> "$MOCK_LOG"
case "$*" in
  *"pip install"*)
    if [ "$FAIL_INSTALL" = 1 ]; then
      exit 19
    fi
    ;;
esac
if [ -n "$FAIL_OPERATION" ]; then
  case "$*" in
    *"$FAIL_OPERATION"*) exit 23 ;;
  esac
fi
exit 0
"""
            )
            mock.chmod(0o755)

            log = root / "operations.log"

            script = """
set -Eeuo pipefail

REPO=/fixture/repository
VENV=/fixture/venv
DB=/fixture/state.sqlite3
API=universalddns-api
WORKER=universalddns-worker
BEFORE=original-commit
BACKUP="$FIXTURE_BACKUP"

verify_service_imports() {
    return 0
}

wait_for_api() {
    return 0
}

""" + rollback_function() + """

# Simulate an upgrade command failing after the rollback
# handler has been installed.
trap rollback ERR
false
"""

            env = os.environ.copy()
            env["PATH"] = str(root) + os.pathsep + env["PATH"]
            env["MOCK_LOG"] = str(log)
            env["FIXTURE_BACKUP"] = str(backup)
            env["FAIL_INSTALL"] = "1" if fail_install else "0"
            env["FAIL_OPERATION"] = fail_operation or ""

            result = subprocess.run(
                ["bash", "-c", script],
                env=env,
                capture_output=True,
                text=True,
            )

            if not log.exists():
                raise AssertionError(
                    "Mock sudo was never executed. "
                    f"Exit: {result.returncode}; "
                    f"stdout: {result.stdout!r}; "
                    f"stderr: {result.stderr!r}"
                )

            operations = log.read_text().splitlines()
            return result, operations

    def test_extracted_function_excludes_preflight(self):
        function = rollback_function()

        self.assertTrue(function.startswith("rollback() {"))
        self.assertTrue(function.rstrip().endswith("}"))
        self.assertNotIn(
            "Preserving currently installed service units",
            function,
        )
        self.assertNotIn(
            "trap rollback ERR",
            function,
        )

    def test_restores_units_before_starting_services(self):
        result, operations = self.run_rollback()

        self.assertEqual(result.returncode, 1)

        api_restore = next(
            i for i, item in enumerate(operations)
            if "install -m 0644" in item
            and "universalddns-api.service" in item
        )

        worker_restore = next(
            i for i, item in enumerate(operations)
            if "install -m 0644" in item
            and "universalddns-worker.service" in item
        )

        daemon_reload = next(
            i for i, item in enumerate(operations)
            if "systemctl daemon-reload" in item
        )

        service_start = next(
            i for i, item in enumerate(operations)
            if "systemctl start" in item
        )

        self.assertLess(api_restore, daemon_reload)
        self.assertLess(worker_restore, daemon_reload)
        self.assertLess(daemon_reload, service_start)

    def test_database_restored_before_service_start(self):
        result, operations = self.run_rollback()

        self.assertEqual(result.returncode, 1)

        db_restore = next(
            i for i, item in enumerate(operations)
            if "state.sqlite3" in item and "install -m 0600" in item
        )

        service_start = next(
            i for i, item in enumerate(operations)
            if "systemctl start" in item
        )

        self.assertLess(db_restore, service_start)

    def test_missing_unit_backup_is_reported(self):
        result, operations = self.run_rollback(
            missing_worker_unit=True
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "Original service-unit backup incomplete",
            result.stderr,
        )

        self.assertFalse(
            any("systemctl daemon-reload" in op for op in operations)
        )

    def test_failed_package_reinstall_preserves_failure(self):
        result, operations = self.run_rollback(fail_install=True)

        self.assertEqual(result.returncode, 1)
        self.assertTrue(
            any("pip install" in op for op in operations)
        )
        self.assertIn("ROLLBACK_ATTEMPTED=YES", result.stdout)



    def test_successful_recovery_operations_are_reported(self):
        result, operations = self.run_rollback()

        self.assertEqual(result.returncode, 1)
        self.assertIn("ROLLBACK_SERVICES=READY", result.stdout)
        self.assertIn("ROLLBACK_OPERATIONS=PASS", result.stdout)
        self.assertNotIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)

    def test_failed_package_reinstall_is_reported(self):
        result, operations = self.run_rollback(fail_install=True)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Package restoration failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertNotIn("ROLLBACK_OPERATIONS=PASS", result.stdout)
        self.assertTrue(
            any("systemctl start" in op for op in operations)
        )

    def test_failed_database_restore_is_reported(self):
        result, operations = self.run_rollback(
            fail_operation="install -m 0600"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Database restoration failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertTrue(
            any("systemctl start" in op for op in operations)
        )

    def test_failed_api_unit_restore_is_reported(self):
        result, operations = self.run_rollback(
            fail_operation="install -m 0644"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("API unit restoration failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertTrue(
            any("systemctl daemon-reload" in op for op in operations)
        )

    def test_failed_systemd_reload_is_reported(self):
        result, operations = self.run_rollback(
            fail_operation="systemctl daemon-reload"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("systemd reload failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertTrue(
            any("systemctl start" in op for op in operations)
        )

    def test_failed_service_restart_is_reported(self):
        result, operations = self.run_rollback(
            fail_operation="systemctl start"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Service restart failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)

    def test_missing_unit_backup_marks_recovery_failed(self):
        result, operations = self.run_rollback(
            missing_worker_unit=True
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "Original service-unit backup incomplete",
            result.stderr,
        )
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)

if __name__ == "__main__":
    unittest.main()
