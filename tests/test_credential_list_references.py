"""The complete credential inventory exposes local selectors without secrets."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from universalddns.token_store import TokenStore


class CredentialListReferenceTests(unittest.TestCase):
    def test_complete_inventory_references_select_exact_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "credentials.db"
            with TokenStore(db) as store:
                first = store.issue("client", frozenset({"records:write"}),
                                    frozenset({"host"}))
                second = store.issue("client", frozenset({"intents:read"}),
                                     frozenset({"other"}))
                inventory = store.list_metadata()
                self.assertEqual(len(inventory), 2)
                self.assertEqual(len({item["reference"] for item in inventory}), 2)
                self.assertEqual(inventory[0]["reference"],
                                 store.blocking_grants("host")[0]["reference"])
                self.assertNotIn(first, repr(inventory))
                self.assertNotIn(second, repr(inventory))
                self.assertNotIn(hashlib.sha256(first.encode()).hexdigest(),
                                 repr(inventory))
                self.assertTrue(store.revoke_reference(inventory[0]["reference"]))
                after = store.list_metadata()
                self.assertTrue(after[0]["revoked"])
                self.assertFalse(after[1]["revoked"])
                self.assertTrue(store.revoke(second))
