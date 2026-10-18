"""Ensure the disposable broker admission gate cannot silently deploy or target lab VMs."""
from pathlib import Path
import subprocess
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tests" / "deployment" / "check-operator-broker-preflight.sh"


class BrokerPreflightContractTests(unittest.TestCase):
    def test_bash_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, timeout=5)

    def test_without_opt_in_is_rejected(self):
        result = subprocess.run(["bash", str(SCRIPT)], capture_output=True,
                                text=True, timeout=5, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("REFUSED:", result.stderr)

    def test_contains_disposable_guest_safeguards(self):
        content = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "UNIVERSALDDNS_DISPOSABLE_BROKER_TEST_V1",
            "uddns-prealpha|uddns-restore-test",
            "uddns-broker-test-*",
            "systemd-detect-virt --vm",
            "/run/systemd/system",
            "operator socket already exists",
            "broker unit already installed",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_rejects_vendor_units_masks_and_dropins(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for path in ("/etc/systemd/system", "/run/systemd/system",
                     "/usr/lib/systemd/system", "/lib/systemd/system"):
            with self.subTest(path=path):
                self.assertIn(path, script)
        self.assertIn('! -L "$base/$unit"', script)
        self.assertIn('! -e "$base/$unit.d"', script)
        self.assertIn('! -L "$base/$unit.d"', script)
        self.assertIn("broker unit drop-in already installed", script)

    def test_gate_has_no_deployment_commands(self):
        content = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("systemctl start", "systemctl enable", "systemctl restart",
                          "systemctl stop", "useradd ", "chmod ", "chown ",
                          "apt-get ", "virsh ", "sudo ", "rm -", "install -"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
