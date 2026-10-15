import tempfile
import unittest
from pathlib import Path

from universalddns.domain import RecordSet
from universalddns.record_catalog import RecordCatalog
from universalddns.record_view import candidate_records


class CandidateRecordTests(unittest.TestCase):
    def test_only_staged_records_join_configured_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            configured = {"static": RecordSet("example.org", "static.example.org",
                                              "A", 60, ("192.0.2.1",))}
            dynamic = RecordSet("example.org", "dynamic.example.org",
                                "AAAA", 120, ("2001:db8::2",))
            with RecordCatalog(Path(temp) / "records.db") as catalog:
                catalog.create("dynamic", dynamic)
                self.assertEqual(candidate_records(configured, catalog), configured)
                catalog.set_active("dynamic", expected_revision=1, active=True)
                combined = candidate_records(configured, catalog)
                self.assertEqual(combined, {**configured, "dynamic": dynamic})
                self.assertEqual(configured.keys(), {"static"})

    def test_configured_identifier_and_rrset_conflicts_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            record = RecordSet("example.org", "same.example.org",
                               "A", 60, ("192.0.2.1",))
            with RecordCatalog(Path(temp) / "records.db") as catalog:
                catalog.create("dynamic", record)
                catalog.set_active("dynamic", expected_revision=1, active=True)
                with self.assertRaises(ValueError):
                    candidate_records({"dynamic": RecordSet(
                        "example.org", "other.example.org", "A", 60,
                        ("192.0.2.4",))}, catalog)
                with self.assertRaises(ValueError):
                    candidate_records({"old": record}, catalog)
