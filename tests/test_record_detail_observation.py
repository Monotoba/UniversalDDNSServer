"""Scoped record details and optional read-only DNS observation."""
import unittest

from fastapi.testclient import TestClient

from universalddns.domain import RecordSet
from universalddns.http_api import APIPrincipal, create_app


class RecordDetailTests(unittest.TestCase):
    def setUp(self):
        self.allowed = RecordSet("example.org", "a.example.org", "A", 60,
                                 ("192.0.2.11",))
        self.hidden = RecordSet("example.org", "b.example.org", "A", 60,
                                ("192.0.2.12",))
        self.records = {"one": self.allowed, "two": self.hidden}
        self.token = "r" * 40
        self.read = APIPrincipal.from_token(
            "viewer", self.token, frozenset({"intents:read"}),
            frozenset({"one"}))
        self.headers = {"Authorization": "Bearer " + self.token}

    def client(self, observer=None, records=None):
        def forbidden(*_args):
            raise AssertionError("details must never invoke mutation")
        return TestClient(create_app(
            forbidden, forbidden, self.records, (self.read,),
            record_reader=lambda: self.records if records is None else records,
            record_observer=observer))

    def test_default_unavailable_and_no_record_values_leak(self):
        with self.client() as client:
            self.assertEqual(client.get("/api/v1/records/one").status_code, 401)
            response = client.get("/api/v1/records/one", headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["authoritative"]["status"], "unavailable")
            self.assertEqual(response.json()["record"]["id"], "one")
            self.assertNotIn("192.0.2.11", response.text)
            self.assertEqual(client.get("/api/v1/records/two",
                                        headers=self.headers).status_code, 404)
            self.assertEqual(client.get("/api/v1/records/missing",
                                        headers=self.headers).status_code, 404)

    def test_optional_observer_results_are_status_only(self):
        for observed, expected in (
            (self.allowed, "matches_template"),
            (self.hidden, "differs_from_template"),
            (None, "absent"),
        ):
            with self.subTest(status=expected):
                with self.client(observer=lambda _record: observed) as client:
                    response = client.get("/api/v1/records/one", headers=self.headers)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["authoritative"]["status"], expected)
                    self.assertNotIn("192.0.2.12", response.text)

    def test_observer_error_reports_unavailable_not_absent(self):
        def failure(_record):
            raise TimeoutError("no DNS answer")
        with self.client(observer=failure) as client:
            response = client.get("/api/v1/records/one", headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["authoritative"]["status"], "unavailable")

    def test_removed_record_not_observed(self):
        called = []
        with self.client(observer=lambda record: called.append(record),
                         records={"two": self.hidden}) as client:
            self.assertEqual(client.get("/api/v1/records/one",
                                        headers=self.headers).status_code, 404)
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
