"""CLI issuance must support active catalog IDs without granting inactive ones."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from universalddns import admin
from universalddns.domain import RecordSet
from universalddns.record_catalog import RecordCatalog
from universalddns.token_store import TokenStore


class CatalogTokenIssuanceTests(unittest.TestCase):
    def test_issue_staged_active_record_and_reject_inactive(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite3"
            static = RecordSet("lab.invalid", "home.lab.invalid", "A",
                               60, ("192.0.2.1",))
            managed = RecordSet("lab.invalid", "dynamic.lab.invalid", "A",
                                60, ("192.0.2.2",))
            settings = SimpleNamespace(database=db, records={"home": static})
            with RecordCatalog(db) as catalog:
                catalog.create("dynamic", managed)
            def issue():
                output = io.StringIO()
                with patch("universalddns.admin.load_settings", return_value=settings), \
                     patch("universalddns.admin.local_operator_identity", return_value="test-operator"), \
                     patch("sys.argv", ["record-token", "--config", "/ignored",
                                        "issue", "--principal", "device",
                                        "--record", "dynamic",
                                        "--scope", "records:write",
                                        "--scope", "intents:read"]), \
                     contextlib.redirect_stdout(output):
                    admin.main()
                return output.getvalue().strip()
            with self.assertRaises(SystemExit) as cm:
                issue()
            self.assertEqual(cm.exception.code, 2)
            with RecordCatalog(db) as catalog:
                catalog.set_active("dynamic", expected_revision=1, active=True)
            token = issue()
            self.assertTrue(token)
            with TokenStore(db) as store:
                identities = store.principals()
                self.assertEqual(len(identities), 1)
                self.assertEqual(identities[0].record_ids, frozenset({"dynamic"}))
                self.assertEqual(identities[0].scopes,
                                 frozenset({"records:write", "intents:read"}))
                self.assertEqual(len(store.list_metadata()), 1)
                self.assertTrue(store.revoke(token))

    def test_unknown_catalog_record_is_not_granted(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = SimpleNamespace(database=Path(tmp) / "state.db",
                                       records={"home": RecordSet(
                                           "lab.invalid", "home.lab.invalid",
                                           "A", 60, ("192.0.2.1",))})
            with patch("universalddns.admin.load_settings", return_value=settings), \
                 patch("sys.argv", ["token-admin", "--config", "/ignored",
                                    "issue", "--principal", "device",
                                    "--record", "missing",
                                    "--scope", "records:write"]):
                with self.assertRaises(SystemExit) as cm:
                    admin.main()
                self.assertEqual(cm.exception.code, 2)
            with TokenStore(settings.database) as store:
                self.assertEqual(store.principals(), ())
