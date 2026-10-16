"""Persist credential lifecycle metadata without exposing bearer secrets."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from universalddns.token_store import TokenStore


class CredentialAuditTests(unittest.TestCase):
    def test_issue_revoke_and_reference_revoke_are_durable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokens.sqlite"
            with TokenStore(path) as tokens:
                one = tokens.issue("alice", frozenset({"records:write"}),
                                   frozenset({"home"}))
                two = tokens.issue("bob", frozenset({"intents:read"}),
                                   frozenset({"second"}))
                reference = tokens.blocking_grants("second")[0]["reference"]
                self.assertTrue(tokens.revoke(one))
                self.assertFalse(tokens.revoke(one))
                self.assertTrue(tokens.revoke_reference(reference))
                self.assertFalse(tokens.revoke_reference(reference))
                rows = tokens.audit_history()
                self.assertEqual([r["action"] for r in rows],
                                 ["revoked", "revoked", "issued", "issued"])
                self.assertEqual([r["principal"] for r in rows],
                                 ["bob", "alice", "bob", "alice"])
                self.assertNotIn(one, repr(rows))
                self.assertNotIn(two, repr(rows))
                self.assertNotIn(hashlib.sha256(one.encode()).hexdigest(),
                                 repr(rows))
            with TokenStore(path) as tokens:
                self.assertEqual(len(tokens.audit_history()), 4)
                self.assertEqual(len(tokens.audit_history(limit=1)), 1)
                for invalid in (0, 1001, True):
                    with self.assertRaises(ValueError):
                        tokens.audit_history(limit=invalid)
