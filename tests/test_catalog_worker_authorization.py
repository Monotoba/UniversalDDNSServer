
"""Worker-side authorization of staged records and revocation."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from universalddns.domain import RecordSet
from universalddns.record_catalog import RecordCatalog
from universalddns.runtime import Policy
from universalddns.token_store import TokenStore


class CatalogWorkerAuthorizationTests(unittest.TestCase):
    def test_active_catalog_permissions_are_rechecked(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "db.sqlite"

            static = RecordSet(
                "example.org",
                "legacy.example.org",
                "A",
                60,
                ("192.0.2.1",),
            )
            managed = RecordSet(
                "example.org",
                "managed.example.org",
                "AAAA",
                120,
                ("2001:db8::1",),
            )
            new_value = RecordSet(
                "example.org",
                "managed.example.org",
                "AAAA",
                120,
                ("2001:db8::2",),
            )

            settings = SimpleNamespace(
                database=db,
                records={"legacy": static},
            )

            with RecordCatalog(db) as catalog:
                catalog.create("dynamic", managed)

            # Initialize credential schema before a policy snapshot.
            with TokenStore(db):
                pass

            policy = Policy.for_settings(settings)

            self.assertFalse(
                policy.may_update("alice", new_value)
            )

            # Activate the record.
            with RecordCatalog(db) as catalog:
                catalog.set_active(
                    "dynamic",
                    expected_revision=1,
                    active=True,
                )

            # Authorize Alice to update this record.
            with TokenStore(db) as tokens:
                token = tokens.issue(
                    "alice",
                    frozenset({"records:write"}),
                    frozenset({"dynamic"}),
                )

            self.assertTrue(
                policy.may_update("alice", new_value)
            )

            # Deactivation must revoke effective authorization
            # immediately, even when an existing policy object is used.
            with RecordCatalog(db) as catalog:
                catalog.set_active(
                    "dynamic",
                    expected_revision=2,
                    active=False,
                )

            self.assertFalse(
                policy.may_update("alice", new_value)
            )

            # Reactivation must not silently restore authorization
            # associated with an outstanding bearer-token grant.
            with RecordCatalog(db) as catalog:
                with self.assertRaisesRegex(
                    ValueError,
                    "revoke existing",
                ):
                    catalog.set_active(
                        "dynamic",
                        expected_revision=3,
                        active=True,
                    )

            # Explicitly revoke the old credential.
            with TokenStore(db) as tokens:
                self.assertTrue(tokens.revoke(token))

            # After revocation, reactivation is permitted.
            with RecordCatalog(db) as catalog:
                catalog.set_active(
                    "dynamic",
                    expected_revision=3,
                    active=True,
                )

            # The revoked token must not regain authorization.
            self.assertFalse(
                policy.may_update("alice", new_value)
            )

    def test_changed_record_key_revokes_old_authorization(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "db.sqlite"

            template = RecordSet(
                "example.org",
                "original.example.org",
                "A",
                60,
                ("192.0.2.1",),
            )
            changed = RecordSet(
                "example.org",
                "renamed.example.org",
                "A",
                60,
                ("192.0.2.1",),
            )

            with RecordCatalog(db) as catalog:
                catalog.create("dynamic", template)
                catalog.set_active(
                    "dynamic",
                    expected_revision=1,
                    active=True,
                )

            with TokenStore(db) as tokens:
                tokens.issue(
                    "alice",
                    frozenset({"records:write"}),
                    frozenset({"dynamic"}),
                )

            policy = Policy.for_settings(
                SimpleNamespace(database=db, records={})
            )

            self.assertTrue(
                policy.may_update("alice", template)
            )

            with RecordCatalog(db) as catalog:
                catalog.update(
                    "dynamic",
                    changed,
                    expected_revision=2,
                )

            self.assertFalse(
                policy.may_update("alice", template)
            )
            self.assertTrue(
                policy.may_update("alice", changed)
            )


if __name__ == "__main__":
    unittest.main()
