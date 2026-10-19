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
    # The rollback function has a top-level closing brace.
    # Do not depend on the comments or preflight code following it.
    end = source.index("\n}\n", start)
    return source[start:end + 2]


class RollbackFaultInjectionTests(unittest.TestCase):

    def run_rollback(self, *, missing_worker_unit=False, fail_install=False, fail_operation=None, missing_wheel=False, bad_checksum=False, fail_checksum=False, missing_db=False, bad_db_checksum=False, snapshot_ready=True, fail_wheel_checksum=False, fail_db_checksum=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            backup = root / "backup"
            backup.mkdir()
            db_backup = root / "db-backup"
            db_backup.mkdir()

            # A recovery wheel must exist before rollback is armed.
            # The mocked sudo command handles checksum verification.
            recovery_wheel = backup / "universalddnsserver-0.3.0a1-py3-none-any.whl"
            if not missing_wheel:
                recovery_wheel.write_bytes(b"fixture-recovery-wheel")

            if not missing_db:
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
  *"sha256sum"*)
    if [ "$FAIL_CHECKSUM" = 1 ]; then exit 24; fi
    case "$*" in
      *"state.sqlite3"*)
        if [ "$FAIL_DB_CHECKSUM" = 1 ]; then exit 24; fi ;;
      *)
        if [ "$FAIL_WHEEL_CHECKSUM" = 1 ]; then exit 24; fi ;;
    esac
    echo "fixture-checksum  $RECOVERY_WHEEL"
    exit 0
    ;;
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
DB_BACKUP="$FIXTURE_DB_BACKUP"
RECOVERY_WHEEL="$FIXTURE_RECOVERY_WHEEL"
RECOVERY_SHA="$FIXTURE_RECOVERY_SHA"
DB_RECOVERY_SHA="$FIXTURE_DB_RECOVERY_SHA"
DB_SNAPSHOT_READY="$FIXTURE_DB_SNAPSHOT_READY"

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
            env["FIXTURE_DB_BACKUP"] = str(db_backup)
            env["FIXTURE_RECOVERY_WHEEL"] = str(recovery_wheel)
            env["FIXTURE_RECOVERY_SHA"] = (
                "unexpected-checksum" if bad_checksum
                else "fixture-checksum"
            )
            env["FIXTURE_DB_RECOVERY_SHA"] = (
                "invalid-db-checksum" if bad_db_checksum
                else "fixture-checksum"
            )
            env["FIXTURE_DB_SNAPSHOT_READY"] = (
                "1" if snapshot_ready else "0"
            )
            env["FAIL_INSTALL"] = "1" if fail_install else "0"
            env["FAIL_OPERATION"] = fail_operation or ""
            env["FAIL_CHECKSUM"] = "1" if fail_checksum else "0"
            env["FAIL_WHEEL_CHECKSUM"] = "1" if fail_wheel_checksum else "0"
            env["FAIL_DB_CHECKSUM"] = "1" if fail_db_checksum else "0"

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

    def test_missing_recovery_wheel_is_reported(self):
        result, operations = self.run_rollback(missing_wheel=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Package restoration failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertFalse(any("pip install" in op for op in operations))

    def test_invalid_recovery_checksum_is_reported(self):
        result, operations = self.run_rollback(bad_checksum=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Package restoration failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertFalse(any("pip install" in op for op in operations))

    def test_recovery_install_uses_offline_wheel(self):
        result, operations = self.run_rollback()
        self.assertEqual(result.returncode, 1)
        installs = [op for op in operations if "pip install" in op]
        self.assertEqual(len(installs), 1)
        self.assertIn("--no-index", installs[0])
        self.assertIn("--no-deps", installs[0])
        self.assertIn("--force-reinstall", installs[0])
        self.assertIn("universalddnsserver-0.3.0a1", installs[0])
        self.assertNotIn("/fixture/repository", installs[0])

    def test_failed_checksum_command_reports_incomplete_recovery(self):
        result, operations = self.run_rollback(fail_checksum=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Package restoration failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertIn("ROLLBACK_ATTEMPTED=YES", result.stdout)
        self.assertFalse(any("pip install" in op for op in operations))
        self.assertTrue(any("state.sqlite3" in op for op in operations))
        self.assertTrue(any("daemon-reload" in op for op in operations))
        self.assertFalse(any("systemctl start" in op for op in operations))
        self.assertIn(
            "ROLLBACK_SERVICES=BLOCKED_DATABASE_RECOVERY",
            result.stderr
        )


    def test_wheel_checksum_failure_does_not_block_database(self):
        result, operations = self.run_rollback(
            fail_wheel_checksum=True
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Package restoration failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertFalse(any(
            "pip install" in op for op in operations
        ))
        self.assertTrue(any(
            "/fixture/venv/bin/python" in op and "state.sqlite3" in op
            for op in operations
        ))
        self.assertFalse(any(
            "systemctl start" in op for op in operations
        ))

        self.assertIn(
            "ROLLBACK_SERVICES=BLOCKED_INCOMPLETE_RECOVERY",
            result.stderr
        )

    def test_database_checksum_failure_blocks_services(self):
        result, operations = self.run_rollback(
            fail_db_checksum=True
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "Protected database snapshot verification failed",
            result.stderr
        )
        self.assertIn(
            "ROLLBACK_SERVICES=BLOCKED_DATABASE_RECOVERY",
            result.stderr
        )
        self.assertFalse(any(
            "/fixture/venv/bin/python" in op and "state.sqlite3" in op
            for op in operations
        ))
        self.assertFalse(any(
            "systemctl start" in op for op in operations
        ))

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
            if "/fixture/venv/bin/python" in item and "state.sqlite3" in item
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

    def test_failed_git_restore_blocks_services(self):
        result, operations = self.run_rollback(
            fail_operation="git -C"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Git restoration failed", result.stderr)
        self.assertIn(
            "ROLLBACK_SERVICES=BLOCKED_INCOMPLETE_RECOVERY",
            result.stderr
        )
        self.assertFalse(any(
            "systemctl start" in op for op in operations
        ))

    def test_failed_package_reinstall_is_reported(self):
        result, operations = self.run_rollback(fail_install=True)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Package restoration failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertNotIn("ROLLBACK_OPERATIONS=PASS", result.stdout)
        self.assertFalse(
            any("systemctl start" in op for op in operations)
        )


        self.assertIn(
            "ROLLBACK_SERVICES=BLOCKED_INCOMPLETE_RECOVERY",
            result.stderr
        )

    def test_missing_protected_database_is_not_restored(self):
        result, operations = self.run_rollback(missing_db=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "ROLLBACK_SERVICES=BLOCKED_DATABASE_RECOVERY",
            result.stderr
        )
        self.assertFalse(any(
            "systemctl start" in op for op in operations
        ))

        self.assertIn(
            "Protected database snapshot verification failed",
            result.stderr
        )
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertFalse(any(
            "/fixture/venv/bin/python" in op and "state.sqlite3" in op
            for op in operations
        ))

    def test_corrupt_database_checksum_blocks_restore(self):
        result, operations = self.run_rollback(
            bad_db_checksum=True
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "ROLLBACK_SERVICES=BLOCKED_DATABASE_RECOVERY",
            result.stderr
        )
        self.assertFalse(any(
            "systemctl start" in op for op in operations
        ))

        self.assertIn(
            "Protected database snapshot verification failed",
            result.stderr
        )
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertFalse(any(
            "/fixture/venv/bin/python" in op and "state.sqlite3" in op
            for op in operations
        ))


    def test_incomplete_snapshot_skips_database_restore(self):
        result, operations = self.run_rollback(
            snapshot_ready=False
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "ROLLBACK_DATABASE=SKIPPED_NO_VERIFIED_SNAPSHOT",
            result.stdout
        )
        self.assertFalse(any(
            "/fixture/venv/bin/python" in op and "state.sqlite3" in op
            for op in operations
        ))
        self.assertTrue(any(
            "systemctl start" in op
            for op in operations
        ))

    def test_failed_database_restore_is_reported(self):
        result, operations = self.run_rollback(
            fail_operation="/fixture/venv/bin/python"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "ROLLBACK_SERVICES=BLOCKED_DATABASE_RECOVERY",
            result.stderr
        )
        self.assertFalse(any(
            "systemctl start" in op for op in operations
        ))

        self.assertIn("Database restoration failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)


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

        self.assertFalse(
            any("systemctl start" in op for op in operations)
        )
        self.assertIn(
            "ROLLBACK_SERVICES=BLOCKED_INCOMPLETE_RECOVERY",
            result.stderr
        )

    def test_failed_systemd_reload_is_reported(self):
        result, operations = self.run_rollback(
            fail_operation="systemctl daemon-reload"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("systemd reload failed", result.stderr)
        self.assertIn("ROLLBACK_OPERATIONS=FAILED", result.stderr)
        self.assertFalse(
            any("systemctl start" in op for op in operations)
        )

        self.assertIn(
            "ROLLBACK_SERVICES=BLOCKED_INCOMPLETE_RECOVERY",
            result.stderr
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

        self.assertIn(
            "ROLLBACK_SERVICES=BLOCKED_INCOMPLETE_RECOVERY",
            result.stderr
        )
        self.assertFalse(
            any("systemctl start" in op for op in operations)
        )


if __name__ == "__main__":
    unittest.main()
