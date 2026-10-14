"""Credential inventory must never reveal bearer secrets or token digests."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from universalddns.token_store import TokenStore


class CredentialMetadataTests(unittest.TestCase):
    def test_inventory_excludes_sensitive_token_material(self):
        with tempfile.TemporaryDirectory() as directory:
            with TokenStore(Path(directory) / "tokens.db") as store:
                token = store.issue("client", frozenset({"records:write"}),
                                    frozenset({"home"}))
                active = store.list_metadata()
                self.assertEqual(1, len(active))
                self.assertEqual("client", active[0]["principal"])
                self.assertEqual(["records:write"], active[0]["scopes"])
                self.assertEqual(["home"], active[0]["records"])
                self.assertFalse(active[0]["revoked"])
                self.assertNotIn(token, repr(active))
                self.assertNotIn(hashlib.sha256(token.encode()).hexdigest(), repr(active))
                self.assertTrue(store.revoke(token))
                revoked = store.list_metadata()
                self.assertTrue(revoked[0]["revoked"])


if __name__ == "__main__":
    unittest.main()
