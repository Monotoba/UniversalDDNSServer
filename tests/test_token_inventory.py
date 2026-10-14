"""Credential inventory must never reveal bearer secrets or token digests."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from universalddns.token_store import TokenStore
from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.orchestrator import UpdateOrchestrator
from universalddns.intents import PermissionDenied, UpdateState


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

    def test_revocation_blocks_pending_publication_but_new_token_recovers_authorization(self):
        class Authorization:
            def __init__(self, store):
                self.store = store

            def may_update(self, principal_id, rrset):
                return any(p.identifier == principal_id and
                           "records:write" in p.scopes and "home" in p.record_ids
                           for p in self.store.principals())

        class Backend:
            class capabilities:
                supported_record_types = frozenset({"A"})

            def __init__(self):
                self.writes = 0

            def publish(self, rrset):
                self.writes += 1

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            with TokenStore(path) as store, SQLiteIntentJournal(path) as journal:
                original = store.issue("client", frozenset({"records:write"}),
                                       frozenset({"home"}))
                backend = Backend()
                service = UpdateOrchestrator(Authorization(store), journal, backend)
                rrset = RecordSet("lab.invalid", "home.lab.invalid", "A", 60,
                                  ("192.0.2.42",))
                first = service.submit("client", rrset)
                self.assertTrue(store.revoke(original))
                with self.assertRaises(PermissionDenied):
                    service.apply(first.identifier)
                self.assertEqual(0, backend.writes)
                self.assertEqual(UpdateState.FAILED, journal.get(first.identifier).state)
                replacement = store.issue("client", frozenset({"records:write"}),
                                          frozenset({"home"}))
                self.assertNotEqual(original, replacement)
                second = service.submit("client", rrset)
                service.apply(second.identifier)
                self.assertEqual(1, backend.writes)


if __name__ == "__main__":
    unittest.main()
