"""Staged records appear in read-only discovery, never in update intake."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.http_api import create_app
from universalddns.record_catalog import RecordCatalog
from universalddns.record_snapshot import catalog_snapshot
from universalddns.token_store import TokenStore


class CatalogDiscoveryTests(unittest.TestCase):
    def test_staged_record_discovery_revocation_and_no_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            static = {"old": RecordSet("example.org", "old.example.org",
                                       "A", 60, ("192.0.2.1",))}
            staged = RecordSet("example.org", "new.example.org",
                               "AAAA", 120, ("2001:db8::12",))
            with RecordCatalog(path) as catalog:
                catalog.create("new", staged)
            with TokenStore(path) as store:
                token = store.issue("alice",
                                    frozenset({"intents:read", "records:write"}),
                                    frozenset({"new"}))

            def principals():
                with TokenStore(path) as store:
                    return store.principals()

            def reader():
                mapping, _ = catalog_snapshot(path, static)
                return mapping

            def journal():
                return SQLiteIntentJournal(path)

            app = create_app(journal, lambda _j: None, static, principals,
                             record_reader=reader)
            headers = {"Authorization": "Bearer " + token}
            with TestClient(app) as client:
                # A token explicitly scoped to an inactive record cannot discover it.
                with self.assertRaisesRegex(ValueError, "unknown record"):
                    client.get("/api/v1/records", headers=headers)
                with RecordCatalog(path) as catalog:
                    catalog.set_active("new", expected_revision=1, active=True)
                result = client.get("/api/v1/records", headers=headers)
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json(), {"records": [
                    {"id": "new", "name": "new.example.org.", "type": "AAAA",
                     "ttl": 120}
                ]})
                # Discovery never expands the existing static update routing.
                self.assertEqual(client.put(
                    "/api/v1/records/new/address", headers=headers,
                    json={"address": "2001:db8::13", "request_id": "attempt"}
                ).status_code, 404)
                with TokenStore(path) as store:
                    store.revoke(token)
                self.assertEqual(client.get("/api/v1/records",
                                            headers=headers).status_code, 401)
