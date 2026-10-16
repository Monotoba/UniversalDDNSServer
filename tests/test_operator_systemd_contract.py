"""Non-deploying checks for the experimental systemd operator broker units.

These tests inspect repository unit files; they do not start systemd or modify VMs.
"""
import configparser
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
UNIT_DIR = ROOT / "deploy" / "systemd"


def load_unit(name):
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    with (UNIT_DIR / name).open(encoding="utf-8") as source:
        parser.read_file(source)
    return parser


class OperatorSystemdContractTests(unittest.TestCase):
    def test_socket_is_opt_in_and_never_listens_on_network(self):
        socket = load_unit("universalddns-operator.socket")
        section = socket["Socket"]
        self.assertEqual(section["ListenStream"], "/run/universalddns/operator.sock")
        self.assertEqual(section["SocketUser"], "universalddns")
        self.assertEqual(section["SocketGroup"], "universalddns-operators")
        self.assertEqual(section["SocketMode"], "0660")
        self.assertEqual(section["DirectoryMode"], "0711")
        self.assertEqual(section["FileDescriptorName"], "operator")
        self.assertEqual(section["Service"], "universalddns-operator.service")
        self.assertEqual(section["RemoveOnStop"], "yes")
        for key in section:
            if key.startswith("Listen"):
                self.assertEqual(key, "ListenStream", "unexpected socket listener")
        self.assertNotIn("Accept", section)
        self.assertEqual(socket["Install"]["WantedBy"], "sockets.target")

    def test_service_is_a_non_root_af_unix_only_broker(self):
        service = load_unit("universalddns-operator.service")
        settings = service["Service"]
        self.assertEqual(settings["User"], "universalddns")
        self.assertEqual(settings["Group"], "universalddns")
        self.assertEqual(settings["RestrictAddressFamilies"], "AF_UNIX")
        self.assertEqual(settings["NoNewPrivileges"], "yes")
        self.assertEqual(settings["ProtectSystem"], "strict")
        self.assertEqual(settings["ProtectHome"], "yes")
        self.assertEqual(settings["RestrictSUIDSGID"], "yes")
        self.assertEqual(settings["UMask"], "0077")
        self.assertEqual(
            settings["ExecStart"],
            "/opt/universalddns/venv/bin/python -m universalddns.operator_broker_service",
        )
        self.assertEqual(service["Unit"]["Requires"], "universalddns-operator.socket")
        self.assertEqual(service["Unit"]["After"], "universalddns-operator.socket")
        self.assertNotIn("ExecStartPre", settings)
        self.assertNotIn("ExecStartPost", settings)

    def test_socket_is_not_silently_installed_by_service(self):
        service = load_unit("universalddns-operator.service")
        self.assertNotIn("Install", service, "broker service must not be separately enabled")


if __name__ == "__main__":
    unittest.main()
