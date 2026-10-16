"""Non-provisioning safety tests for the disposable broker VM wrapper."""
from pathlib import Path
import subprocess
import unittest

SCRIPT = (Path(__file__).resolve().parents[1] / "tests" / "deployment"
          / "create-broker-test-vm.sh")


class BrokerVMProvisioningTests(unittest.TestCase):
    def run_refusal(self, *args):
        result = subprocess.run(["bash", str(SCRIPT), *args],
                                capture_output=True, text=True, timeout=5, check=False)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("REFUSED:", result.stderr)

    def test_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, timeout=5)

    def test_requires_opt_in(self):
        self.run_refusal()

    def test_protected_vm_name_refused(self):
        for name in ("uddns-prealpha", "uddns-restore-test", "uddns-broker-test-",
                     "../uddns-broker-test-x", "uddns-broker-test-X"):
            with self.subTest(name=name):
                self.run_refusal("--create-disposable", name)

    def test_wrapper_invokes_only_existing_guarded_creator(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('VM="$name" bash "$repo/tests/deployment/create-vm.sh"', source)
        self.assertIn('virsh -c qemu:///system dominfo "$name"', source)
        self.assertIn('sudo test -e "$file"', source)
        self.assertNotIn("virsh destroy", source)
        self.assertNotIn("virsh undefine", source)
        self.assertNotIn("qemu-img create", source)


if __name__ == "__main__":
    unittest.main()
