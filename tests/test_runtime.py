import json
import os
import tempfile
import unittest
from pathlib import Path

from universalddns.runtime import load_settings, factories
from universalddns.token_store import TokenStore
from universalddns.domain import RecordSet

class RuntimeTests(unittest.TestCase):
    def test_config_and_live_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            secret = root / "secret.json"
            secret.write_text(json.dumps({"key_secret": "YWFhYWFhYWFhYWFhYQ=="}))
            os.chmod(secret, 0o600)
            cfg = root / "config.json"
            data = {
                "database": str(root / "db.sqlite3"),
                "credentials": str(secret),
                "dns": {"zone": "example.test", "server": "127.0.0.1",
                        "port": 15353, "key_name": "ddns-key."},
                "interval": 1,
                "records": {"host": {"name": "host.example.test", "type": "A",
                                     "ttl": 60, "address": "192.0.2.1"}}
            }
            cfg.write_text(json.dumps(data))
            settings = load_settings(cfg)
            journal, orchestrator, principals = factories(settings)
            with TokenStore(settings.database) as store:
                token = store.issue("alice", frozenset({"records:write"}),
                                    frozenset({"host"}))
            self.assertEqual(len(principals()), 1)
            with journal() as instance:
                service = orchestrator(instance)
                allowed = RecordSet("example.test", "host.example.test",
                                    "A", 60, ("192.0.2.2",))
                self.assertTrue(service._authorizer.may_update("alice", allowed))
            with TokenStore(settings.database) as store:
                store.revoke(token)
            self.assertEqual(principals(), ())
            alias = root / "linked-secret.json"
            alias.symlink_to(secret)
            data["credentials"] = str(alias)
            cfg.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                load_settings(cfg)
            data["credentials"] = str(secret)
            cfg.write_text(json.dumps(data))
            os.chmod(secret, 0o644)
            with self.assertRaises(PermissionError):
                load_settings(cfg)

    def test_reject_relative_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config.json"
            config.write_text(json.dumps({"database": "state.db"}))
            with self.assertRaises(ValueError):
                load_settings(config)
