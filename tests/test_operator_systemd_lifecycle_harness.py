"""Guard the opt-in disposable systemd smoke harness from accidental execution."""
from pathlib import Path
import subprocess
import unittest


SCRIPT = (Path(__file__).resolve().parents[1] / "tests" / "deployment"
          / "test-operator-systemd-lifecycle.sh")


class DisposableSystemdLifecycleContractTests(unittest.TestCase):
    def test_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], timeout=5, check=True)

    def test_no_argument_cannot_run(self):
        result = subprocess.run(["bash", str(SCRIPT)], capture_output=True,
                                text=True, timeout=5, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("explicit opt-in required", result.stderr)

    def test_admission_precedes_mutation(self):
        script = SCRIPT.read_text(encoding="utf-8")
        preflight = script.index("check-operator-broker-preflight.sh")
        first_mutation = script.index("sudo install")
        self.assertLess(preflight, first_mutation)
        self.assertIn("trap cleanup EXIT", script)
        self.assertIn("RemoveOnStop failed", script)
        self.assertIn("sudo systemctl daemon-reload", script)


if __name__ == "__main__":
    unittest.main()
