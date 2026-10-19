"""Safety contract tests for the disposable VM upgrade script."""

from pathlib import Path
import unittest
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests/deployment/update-vm.sh"


class VMUpgradeSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text()

    def test_recovery_wheel_precedes_service_shutdown(self):
        script = self.script
        preflight = script.index('echo "Preparing offline recovery wheel"')
        build = script.index('/usr/bin/python3 -m pip wheel')
        validated = script.index('echo "RECOVERY_PREFLIGHT=PASS"')
        shutdown = script.index(
            'sudo systemctl stop "$WORKER" "$API"',
            script.index("trap rollback ERR")
        )
        self.assertLess(preflight, build)
        self.assertLess(build, validated)
        self.assertLess(validated, shutdown)

    def test_recovery_preflight_is_outside_rollback_trap(self):
        script = self.script
        preflight = script.index('echo "Preparing offline recovery wheel"')
        armed = script.index("trap rollback ERR")
        self.assertLess(preflight, armed)
        self.assertIn("set -Eeuo pipefail", script)

    def test_recovery_install_is_offline_only(self):
        rollback = self.script.split("rollback() {", 1)[1]
        rollback = rollback.split(
            'echo "Preparing offline recovery wheel"', 1
        )[0]
        self.assertIn("--no-index --no-deps --force-reinstall", rollback)
        self.assertIn('"$RECOVERY_WHEEL"', rollback)
        self.assertIn('"$RECOVERY_SHA"', rollback)

    def test_installer_sets_readable_umask(self):
        self.assertIn("umask 022", self.script)
        self.assertIn(
            """sudo sh -c 'umask 022; exec "$@"'""",
            self.script,
        )

    def test_service_account_import_validation(self):
        self.assertIn(
            "verify_service_imports() {",
            self.script,
        )
        self.assertIn(
            'sudo -u universalddns "$VENV/bin/python"',
            self.script,
        )
        self.assertIn(
            "from universalddns.runtime import api_app",
            self.script,
        )

    def test_import_check_precedes_service_restart(self):
        upgrade = self.script.split(
            'sudo git -C "$REPO" merge --ff-only "$AFTER"',
            1,
        )[1]

        import_check = upgrade.index("verify_service_imports")
        service_start = upgrade.index(
            'sudo systemctl start "$API" "$WORKER"'
        )

        self.assertLess(import_check, service_start)

    def test_original_unit_files_are_preserved(self):
        self.assertIn(
            '"$BACKUP/universalddns-api.service"',
            self.script,
        )
        self.assertIn(
            '"$BACKUP/universalddns-worker.service"',
            self.script,
        )

    def test_rollback_restores_units_before_restart(self):
        rollback = self.script.split("rollback() {", 1)[1]
        rollback = rollback.split("trap rollback ERR", 1)[0]

        self.assertIn(
            'sudo systemctl daemon-reload',
            rollback,
        )

        self.assertLess(
            rollback.index(
                '"$BACKUP/universalddns-api.service"'
            ),
            rollback.index(
                'sudo systemctl start "$API" "$WORKER"'
            ),
        )

        self.assertLess(
            rollback.index(
                '"$BACKUP/universalddns-worker.service"'
            ),
            rollback.index(
                'sudo systemctl start "$API" "$WORKER"'
            ),
        )

    def test_rollback_preserves_failure_status(self):
        rollback = self.script.split("rollback() {", 1)[1]
        rollback = rollback.split("trap rollback ERR", 1)[0]

        self.assertIn("local status=$?", rollback)
        self.assertIn('exit "$status"', rollback)


    def test_privileged_install_wrapper_overrides_umask(self):
        """The actual shell wrapper must override restrictive umask."""
        import os
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "installed"
            destination.mkdir()

            program = (
                "import pathlib,sys; "
                "p=pathlib.Path(sys.argv[1]); "
                "p.mkdir(); "
                "(p/'runtime.py').write_text('pass\\\\n')"
            )

            result = subprocess.run(
                [
                    "sh", "-c",
                    'umask 022; exec "$@"',
                    "sh",
                    sys.executable,
                    "-c",
                    program,
                    str(destination / "universalddns"),
                ],
                capture_output=True,
                text=True,
                preexec_fn=lambda: os.umask(0o077),
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            package = destination / "universalddns"
            runtime = package / "runtime.py"

            self.assertEqual(package.stat().st_mode & 0o777, 0o755)
            self.assertEqual(runtime.stat().st_mode & 0o777, 0o644)

    def test_restrictive_umask_reproduces_failure(self):
        """Without the wrapper, default filesystem permissions fail."""
        import os
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "universalddns"

            program = (
                "import pathlib,sys; "
                "p=pathlib.Path(sys.argv[1]); "
                "p.mkdir(); "
                "(p/'runtime.py').write_text('pass\\\\n')"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    program,
                    str(destination),
                ],
                capture_output=True,
                text=True,
                preexec_fn=lambda: os.umask(0o077),
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            self.assertEqual(
                destination.stat().st_mode & 0o777,
                0o700,
            )

            self.assertEqual(
                (destination / "runtime.py").stat().st_mode & 0o777,
                0o600,
            )


    def test_sqlite_snapshot_uses_backup_api(self):
        self.assertIn("src.backup(dst)", self.script)
        self.assertIn(
            'PRAGMA integrity_check',
            self.script
        )

    def test_database_snapshot_precedes_git_merge(self):
        self.assertLess(
            self.script.index("DB_SNAPSHOT_READY=1"),
            self.script.index(
                'git -C "$REPO" merge --ff-only'
            )
        )



    def test_production_updater_excludes_fault_injection(self):
        script = self.script

        self.assertNotIn("UDDNS_FAULT_INJECTION", script)
        self.assertNotIn("FAULT_INJECTION=AFTER_GIT_MERGE", script)
        self.assertNotIn(
            ".universalddns-allow-fault-injection",
            script
        )

        merge = 'sudo git -C "$REPO" merge --ff-only "$AFTER"'
        install = (
            'sudo sh -c \'umask 022; exec "$@"\' sh \\'
        )

        self.assertEqual(script.count(merge), 1)
        self.assertEqual(script.count(install), 3)
        self.assertIn(
            'PIP_ENV=()',
            script
        )
        self.assertIn(
            'PIP_ENV+=("PIP_NO_INDEX=$PIP_NO_INDEX")',
            script
        )
        self.assertIn(
            'PIP_ENV+=("PIP_FIND_LINKS=$PIP_FIND_LINKS")',
            script
        )
        self.assertIn(
            '/usr/bin/env "${PIP_ENV[@]}"',
            script
        )
        self.assertIn(
            '"$VENV/bin/python" -m pip install \\',
            script
        )
        self.assertLess(
            script.index(merge),
            script.index('/usr/bin/env "${PIP_ENV[@]}"')
        )


    def test_offline_pip_environment_forwarding(self):
        import os
        import subprocess

        script = self.script
        start = script.index("PIP_ENV=()")
        end = script.index(
            "sudo sh -c 'umask 022; exec",
            start,
        )
        fragment = script[start:end]

        cases = (
            ({"PIP_NO_INDEX": "1",
              "PIP_FIND_LINKS": "/root/test-wheelhouse"},
             "1", "/root/test-wheelhouse"),
            ({}, "", ""),
        )

        for settings, expected_index, expected_links in cases:
            with self.subTest(settings=settings):
                env = os.environ.copy()
                env.pop("PIP_NO_INDEX", None)
                env.pop("PIP_FIND_LINKS", None)
                env.update(settings)

                command = (
                    fragment
                    + 'printf "INDEX=%s\\nLINKS=%s\\n" '
                    '"${PIP_ENV[0]#PIP_NO_INDEX=}" '
                    '"${PIP_ENV[1]#PIP_FIND_LINKS=}"\\n'
                )

                if not settings:
                    command = fragment + (
                        'printf "COUNT=%s\\n" "${#PIP_ENV[@]}"\\n'
                    )

                result = subprocess.run(
                    ["bash", "-c", command],
                    env=env,
                    text=True,
                    capture_output=True,
                    check=True,
                )

                if settings:
                    self.assertIn(
                        f"INDEX={expected_index}", result.stdout
                    )
                    self.assertIn(
                        f"LINKS={expected_links}", result.stdout
                    )
                else:
                    self.assertIn("COUNT=0", result.stdout)

    def test_recovery_directory_requires_root_ownership(self):
        script = self.script

        self.assertIn(
            "BACKUP_ROOT=/var/backups/universalddns",
            script
        )
        self.assertIn(
            '[[ -L "$BACKUP_ROOT" ]]',
            script
        )
        self.assertIn(
            '[[ -d "$BACKUP_ROOT" ]] || exit 2',
            script
        )
        self.assertIn(
            "stat -c '%u:%g:%a' \"$BACKUP_ROOT\"",
            script
        )
        self.assertIn(
            '"0:0:700"',
            script
        )
        self.assertIn(
            'install -d -o root -g root -m 0700 "$BACKUP_ROOT"',
            script
        )

        self.assertLess(
            script.index("BACKUP_ROOT=/var/backups/universalddns"),
            script.index('sudo mkdir -m 0700 "$BACKUP"')
        )


    def test_vm_verification_handles_unset_home(self):
        path = ROOT / "tests/deployment/vm-test.sh"
        script = path.read_text()

        self.assertIn('[[ -z "${HOME:-}" ]]', script)
        self.assertIn('getent passwd "$(id -u)"', script)
        self.assertIn('export HOME', script)
        self.assertLess(
            script.index('export HOME'),
            script.index('ROOT="$HOME/uddns-results"')
        )


if __name__ == "__main__":
    unittest.main()
