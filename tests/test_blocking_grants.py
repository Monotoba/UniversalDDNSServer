"""Inventory of credentials that block managed-record reactivation."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from universalddns.token_store import TokenStore


class BlockingGrantsTests(unittest.TestCase):
    def test_only_active_matching_grants_with_no_secrets(self):
        with tempfile.TemporaryDirectory() as root:
            with TokenStore(Path(root) / "state.sqlite") as tokens:
                first = tokens.issue("alice", frozenset({"records:write"}),
                                     frozenset({"inactive", "other"}))
                second = tokens.issue("alice", frozenset({"intents:read"}),
                                      frozenset({"inactive"}))
                unrelated = tokens.issue("bob", frozenset({"records:write"}),
                                         frozenset({"other"}))
                items = tokens.blocking_grants("inactive")
                self.assertEqual(len(items), 2)
                self.assertEqual([item["principal"] for item in items],
                                 ["alice", "alice"])
                self.assertEqual(items[0]["records"], ["inactive", "other"])
                self.assertNotIn(first, repr(items))
                self.assertNotIn(second, repr(items))
                self.assertNotIn(hashlib.sha256(first.encode()).hexdigest(), repr(items))
                tokens.revoke(first)
                self.assertEqual(len(tokens.blocking_grants("inactive")), 1)
                tokens.revoke(second)
                self.assertEqual(tokens.blocking_grants("inactive"), ())
                self.assertEqual(len(tokens.blocking_grants("other")), 1)
                tokens.revoke(unrelated)

    def test_empty_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with TokenStore(Path(root) / "state.sqlite") as tokens:
                with self.assertRaises(ValueError):
                    tokens.blocking_grants("")
