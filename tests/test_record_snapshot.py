"""Consistent active-record and token-grant SQLite snapshots."""
import tempfile
import unittest
from pathlib import Path

from universalddns.domain import RecordSet
from universalddns.record_catalog import RecordCatalog
from universalddns.record_snapshot import catalog_snapshot
from universalddns.token_store import TokenStore


class RecordSnapshotTests(unittest.TestCase):
    def test_snapshot_requires_explicit_grant_and_tracks_revocation(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "records.sqlite"
            template = RecordSet("example.org", "new.example.org", "A",
                                 60, ("192.0.2.99",))
            with RecordCatalog(path) as catalog:
                catalog.create("new", template)
                catalog.set_active("new", expected_revision=1, active=True)
            with TokenStore(path) as tokens:
                token = tokens.issue("alice",
                                     frozenset({"records:write", "intents:read"}),
                                     frozenset({"new"}))
            mapping, principals = catalog_snapshot(path, {})
            self.assertEqual(mapping, {"new": template})
            self.assertEqual(principals[0].record_ids, frozenset({"new"}))
            with TokenStore(path) as tokens:
                self.assertTrue(tokens.revoke(token))
            mapping, principals = catalog_snapshot(path, {})
            self.assertEqual(mapping, {"new": template})
            self.assertEqual(principals, ())

    def test_stale_token_and_static_conflict_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "records.sqlite"
            item = RecordSet("example.org", "new.example.org", "AAAA",
                             120, ("2001:db8::10",))
            with RecordCatalog(path) as catalog:
                catalog.create("new", item)
                catalog.set_active("new", expected_revision=1, active=True)
            with TokenStore(path) as tokens:
                tokens.issue("alice", frozenset({"intents:read"}),
                             frozenset({"unknown"}))
            mapping, principals = catalog_snapshot(path, {})
            self.assertEqual(mapping, {"new": item})
            self.assertEqual(principals[0].record_ids, frozenset({"unknown"}))
            with self.assertRaises(ValueError):
                catalog_snapshot(path, {"static": item})
