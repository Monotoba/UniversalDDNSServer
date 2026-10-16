"""Exercise the VM scratch-only lifecycle script in unit-test CI."""
import subprocess
import sys
import unittest
from pathlib import Path


class VMFixtureLifecycleTests(unittest.TestCase):
    def test_scratch_only_catalog_credential_workflow(self):
        script = Path(__file__).resolve().parent / "deployment" / "check-catalog-lifecycle.py"
        result = subprocess.run([sys.executable, str(script)], check=False,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: isolated SQLite catalog/credential lifecycle", result.stdout)
