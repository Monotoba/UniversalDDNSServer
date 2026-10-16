"""Credential references support local revocation without bearing token secrets."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from universalddns.token_store import TokenStore


class ReferenceRevocationTests(unittest.TestCase):
    def test_revoke_only_selected_credential_and_hide_digest(self):
        with tempfile.TemporaryDirectory() as root:
            with TokenStore(Path(root) / "db.sqlite") as store:
                first = store.issue("alice", frozenset({"records:write"}),
                                    frozenset({"dynamic"}))
                second = store.issue("alice", frozenset({"intents:read"}),
                                     frozenset({"dynamic"}))
                blockers = store.blocking_grants("dynamic")
                self.assertEqual(len(blockers), 2)
                ref = blockers[0]["reference"]
                self.assertTrue(ref.startswith("cred-"))
                self.assertNotIn(first, repr(blockers))
                self.assertNotIn(hashlib.sha256(first.encode()).hexdigest(), repr(blockers))
                self.assertTrue(store.revoke_reference(ref))
                self.assertFalse(store.revoke_reference(ref))
                self.assertEqual(len(store.blocking_grants("dynamic")), 1)
                self.assertEqual(len(store.principals()), 1)
                self.assertTrue(store.revoke(second))
                for invalid in ("", "cred-0", "cred--1", "cred-foobar", "cred-" + "f"*64):
                    with self.subTest(invalid=invalid):
                        with self.assertRaises(ValueError):
                            store.revoke_reference(invalid)
