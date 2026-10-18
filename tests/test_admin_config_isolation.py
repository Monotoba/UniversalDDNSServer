"""Local administration must never require access to the DNS publishing key."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universalddns.runtime import load_admin_settings, load_settings
from universalddns.record_catalog import RecordCatalog
from universalddns.domain import RecordSet
from universalddns import admin, record_admin


class AdministrativeConfigIsolationTests(unittest.TestCase):
    def test_admin_does_not_load_tsIG_and_publisher_still_requires_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = root / "config.json"
            secret = root / "protected-does-not-exist.json"
            cfg.write_text(json.dumps({
                "database": str(root / "state.sqlite3"),
                "credentials": str(secret),
                "dns": {"zone": "lab.invalid", "server": "127.0.0.1",
                        "port": 53, "key_name": "lab-key."},
                "interval": 1,
                "records": {"home": {"name": "home.lab.invalid",
                                     "type": "A", "ttl": 60,
                                     "address": "192.0.2.1"}}
            }))
            settings = load_admin_settings(cfg)
            self.assertEqual(settings.zone, "lab.invalid.")
            self.assertIn("home", settings.records)
            with self.assertRaises(ValueError):
                load_settings(cfg)
            with patch("sys.argv", ["record-admin", "--config", str(cfg),
                                    "create", "candidate", "--name",
                                    "candidate.lab.invalid", "--type", "A",
                                    "--ttl", "60", "--address", "192.0.2.2"]), \
                 patch.object(record_admin, "local_operator_identity", return_value="operator"):
                self.assertEqual(record_admin.main(), 0)
            with RecordCatalog(settings.database) as catalog:
                self.assertEqual(catalog.get("candidate")[0],
                                 RecordSet("lab.invalid", "candidate.lab.invalid",
                                           "A", 60, ("192.0.2.2",)))
            with patch("sys.argv", ["admin", "--config", str(cfg), "list"]):
                admin.main()

    def test_admin_rejects_secret_path_symlinks_without_reading_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret = root / "secret.json"
            secret.write_text("{}")
            alias = root / "alias.json"
            alias.symlink_to(secret)
            cfg = root / "config.json"
            cfg.write_text(json.dumps({
                "database": str(root / "state.sqlite3"),
                "credentials": str(alias),
                "dns": {"zone": "lab.invalid", "server": "127.0.0.1",
                        "port": 53, "key_name": "lab-key."},
                "interval": 1,
                "records": {"home": {"name": "home.lab.invalid",
                                     "type": "A", "ttl": 60,
                                     "address": "192.0.2.1"}}
            }))
            with self.assertRaises(ValueError):
                load_admin_settings(cfg)
