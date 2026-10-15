"""Scope guards for future active catalog record views."""
import unittest

from universalddns.domain import RecordSet
from universalddns.http_api import APIPrincipal
from universalddns.record_scopes import scoped_records, validate_catalog_grants


class CatalogScopeTests(unittest.TestCase):
    def setUp(self):
        self.configured = {"legacy": RecordSet("example.org", "old.example.org",
                                                "A", 60, ("192.0.2.1",))}
        self.staged = RecordSet("example.org", "new.example.org",
                                "AAAA", 120, ("2001:db8::3",))
        self.candidate = {**self.configured, "staged": self.staged}

    def principal(self, record_ids, scopes=("intents:read",)):
        return APIPrincipal.from_token("alice", "a" * 48, frozenset(scopes),
                                        frozenset(record_ids))

    def test_catalog_entries_do_not_automatically_grant_access(self):
        principal = self.principal(("legacy",))
        self.assertEqual(scoped_records(self.candidate, principal, scope="intents:read"),
                         self.configured)
        self.assertEqual(scoped_records(self.candidate, principal, scope="records:write"), {})
        validate_catalog_grants(self.configured, self.candidate, (principal,))

    def test_explicit_scope_grants_catalog_record(self):
        principal = self.principal(("staged",), ("intents:read", "records:write"))
        self.assertEqual(scoped_records(self.candidate, principal, scope="records:write"),
                         {"staged": self.staged})
        validate_catalog_grants(self.configured, self.candidate, (principal,))

    def test_stale_grants_and_static_replacements_refused(self):
        with self.assertRaisesRegex(ValueError, "unknown record"):
            validate_catalog_grants(self.configured, self.candidate,
                                    (self.principal(("deleted",)),))
        changed = dict(self.candidate)
        changed["legacy"] = self.staged
        with self.assertRaisesRegex(ValueError, "configured record changed"):
            validate_catalog_grants(self.configured, changed, ())
        with self.assertRaisesRegex(ValueError, "unsupported"):
            scoped_records(self.candidate, self.principal(("legacy",)), scope="admin")
