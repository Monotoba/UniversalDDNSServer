"""Regression checks for VM upgrade locking."""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

UPDATER = (
    Path(__file__).resolve().parent
    / "deployment"
    / "update-vm.sh"
)


class VMUpgradeLockTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.script = UPDATER.read_text()

    def test_root_required_for_upgrade(self):
        self.assertIn(
            'if (( EUID != 0 )); then',
            self.script
        )

    def test_lock_is_in_protected_directory(self):
        self.assertIn(
            'LOCK_DIR=/run/lock/universalddns',
            self.script
        )
        self.assertIn(
            'LOCK_FILE="$LOCK_DIR/upgrade.lock"',
            self.script
        )

    def test_lock_directory_security(self):
        script = self.script

        self.assertIn('[[ -L "$LOCK_DIR" ]]', script)
        self.assertIn('[[ -d "$LOCK_DIR" ]] || exit 2', script)
        self.assertIn(
            "stat -c '%u:%g:%a' \"$LOCK_DIR\"",
            script
        )
        self.assertIn('"0:0:700"', script)
        self.assertIn(
            'install -d -o root -g root -m 0700 "$LOCK_DIR"',
            script
        )

        self.assertLess(
            script.index('[[ -L "$LOCK_DIR" ]]'),
            script.index('exec 9>>"$LOCK_FILE"')
        )

    def test_nonblocking_exclusive_lock(self):
        self.assertIn('flock -n 9', self.script)

    def test_lock_precedes_upgrade_operations(self):
        lock = self.script.index('flock -n 9')
        fetch = self.script.index(
            'git -C "$REPO" fetch --prune'
        )
        shutdown = self.script.index(
            'sudo systemctl stop "$WORKER" "$API"',
            self.script.index('trap rollback ERR')
        )
        self.assertLess(lock, fetch)
        self.assertLess(lock, shutdown)

    def test_lock_remains_held_during_rollback(self):
        self.assertNotIn('exec 9>&-', self.script)
        self.assertNotIn('flock -u 9', self.script)

    def test_symlink_lock_is_rejected(self):
        self.assertIn(
            '[[ -L "$LOCK_FILE" ]]',
            self.script
        )



    def test_actual_lock_contention_and_release(self):
        start = self.script.index('exec 9>>"$LOCK_FILE"')
        end = self.script.index(
            'echo "UPGRADE_LOCK=ACQUIRED"', start
        )
        block = self.script[start:end]

        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "upgrade.lock"
            ready = Path(tmp) / "ready"
            release = Path(tmp) / "release"

            holder = (
                "set -Eeuo pipefail\n"
                + block
                + '\ntouch "$READY_FILE"\n'
                + 'while [[ ! -e "$RELEASE_FILE" ]]; do '
                  'sleep 0.05; done\n'
            )

            env = os.environ.copy()
            env.update({
                "LOCK_FILE": str(lock),
                "READY_FILE": str(ready),
                "RELEASE_FILE": str(release),
            })

            proc = subprocess.Popen(
                ["bash", "-c", holder], env=env
            )

            try:
                for _ in range(100):
                    if ready.exists():
                        break
                    if proc.poll() is not None:
                        self.fail("Lock holder exited unexpectedly")
                    time.sleep(0.05)
                else:
                    self.fail("Lock holder timed out")

                contender = subprocess.run(
                    ["flock", "-n", str(lock), "true"],
                    check=False,
                )
                self.assertEqual(contender.returncode, 1)

                release.touch()
                self.assertEqual(proc.wait(timeout=10), 0)

                retry = subprocess.run(
                    ["flock", "-n", str(lock), "true"],
                    check=False,
                )
                self.assertEqual(retry.returncode, 0)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
