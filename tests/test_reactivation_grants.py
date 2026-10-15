"""Catalog reactivation must not resurrect previously authorized token grants."""
import tempfile
import unittest
from pathlib import Path

from universalddns.domain import RecordSet
from universalddns.record_catalog import RecordCatalog
from universalddns.token_store import TokenStore


class ReactivationSafetyTests(unittest.TestCase):
    def test_reactivation_refuses_dormant_grants_until_revoked(self):
        with tempfile.TemporaryDirectory() as root:
            db = Path(root) / "state.sqlite"
            record = RecordSet("lab.invalid", "client.lab.invalid", "A",
                               60, ("192.0.2.2",))
            with RecordCatalog(db) as catalog:
                catalog.create("client", record)
                self.assertEqual(catalog.set_active(
                    "client", expected_revision=1, active=True), 2)
            with TokenStore(db) as tokens:
                token = tokens.issue("device", frozenset({"records:write"}),
                                     frozenset({"client"}))
            with RecordCatalog(db) as catalog:
                self.assertEqual(catalog.set_active(
                    "client", expected_revision=2, active=False), 3)
                with self.assertRaisesRegex(ValueError, "revoke existing"):
                    catalog.set_active("client", expected_revision=3, active=True)
                self.assertEqual(catalog.get("client")[1], 3)
            with TokenStore(db) as tokens:
                self.assertTrue(tokens.revoke(token))
            with RecordCatalog(db) as catalog:
                self.assertEqual(catalog.set_active(
                    "client", expected_revision=3, active=True), 4)

    def test_missing_token_table_does_not_prevent_first_activation(self):
        with tempfile.TemporaryDirectory() as root:
            db = Path(root) / "state.sqlite"
            with RecordCatalog(db) as catalog:
                catalog.create("client", RecordSet(
                    "lab.invalid", "first.lab.invalid", "AAAA",
                    60, ("2001:db8::1",)))
                self.assertEqual(catalog.set_active(
                    "client", expected_revision=1, active=True), 2)
