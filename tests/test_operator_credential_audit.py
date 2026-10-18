"""Verified operator attribution and legacy audit migration."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from universalddns.token_store import TokenStore


class OperatorAuditTests(unittest.TestCase):
    def test_reference_revocation_records_operator_and_other_events_are_unknown(self):
        with tempfile.TemporaryDirectory() as root:
            db = Path(root) / "tokens.db"
            with TokenStore(db) as store:
                token = store.issue("client", frozenset({"records:write"}),
                                    frozenset({"home"}))
                reference = store.blocking_grants("home")[0]["reference"]
                with self.assertRaises(ValueError):
                    store.revoke_reference(reference, operator="")
                self.assertTrue(store.revoke_reference(reference, operator="operator-one"))
                events = store.audit_history()
                self.assertEqual(events[0]["operator"], "operator-one")
                self.assertIsNone(events[1]["operator"])
                self.assertFalse(store.revoke(token))
            with TokenStore(db) as store:
                self.assertEqual(store.audit_history()[0]["operator"], "operator-one")

    def test_existing_audit_table_adds_nullable_operator_column(self):
        with tempfile.TemporaryDirectory() as root:
            db = Path(root) / "old.db"
            with sqlite3.connect(db) as conn:
                conn.execute("""CREATE TABLE credential_audit (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    credential_reference TEXT NOT NULL,
                    principal TEXT NOT NULL,
                    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )""")
                conn.execute("INSERT INTO credential_audit(action,credential_reference,principal) VALUES ('issued','cred-1','legacy')")
            with TokenStore(db) as store:
                history = store.audit_history()
                self.assertEqual(history[0]["principal"], "legacy")
                self.assertIsNone(history[0]["operator"])
