"""Credential lifecycle operations include operator when explicitly supplied."""
import tempfile
import unittest
from pathlib import Path
from universalddns.token_store import TokenStore

class CredentialActorCoverageTests(unittest.TestCase):
    def test_issue_and_bearer_revoke_actor_with_unattributed_library_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TokenStore(Path(tmp) / "tokens.db") as store:
                token = store.issue("client", frozenset({"records:write"}),
                                    frozenset({"home"}), operator="operator-one")
                self.assertTrue(store.revoke(token, operator="operator-two"))
                events = store.audit_history()
                self.assertEqual([event["operator"] for event in events],
                                 ["operator-two", "operator-one"])
                self.assertEqual([event["action"] for event in events],
                                 ["revoked", "issued"])
                second = store.issue("library", frozenset({"intents:read"}),
                                     frozenset({"home"}))
                self.assertTrue(store.revoke(second))
                self.assertIsNone(store.audit_history()[0]["operator"])
                with self.assertRaises(ValueError):
                    store.issue("test", frozenset({"intents:read"}),
                                frozenset({"home"}), operator="bad actor")
                with self.assertRaises(ValueError):
                    store.revoke(token, operator="")
                self.assertEqual(len(store.audit_history()), 4)
