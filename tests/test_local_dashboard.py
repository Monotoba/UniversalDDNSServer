"""Local dashboard security and existing scoped-API contract tests."""
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient

from universalddns.http_api import APIPrincipal, create_app
from universalddns.domain import RecordSet
from universalddns.local_dashboard import (
    PAGE, SCRIPT, dashboard, dashboard_script, require_loopback,
)


class LocalDashboardTests(unittest.TestCase):
    def setUp(self):
        token = "t" * 40
        self.token = token
        self.principal = APIPrincipal.from_token(
            "reader", token, frozenset({"intents:read"}), frozenset({"allowed"}))
        records = {
            "allowed": RecordSet("example.org", "ok.example.org", "A", 60, ("192.0.2.1",)),
            "hidden": RecordSet("example.org", "secret.example.org", "A", 60, ("192.0.2.2",)),
        }
        # The read-only routes do not instantiate a journal or orchestrator.
        def forbidden(*_args):
            raise AssertionError("read-only dashboard must not write")

        self.app = create_app(forbidden, forbidden, records, (self.principal,))
        self.client = TestClient(self.app, base_url="http://127.0.0.1")
        self.addCleanup(self.client.close)

    def test_dashboard_has_no_embedded_credentials_and_disables_caching(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])
        self.assertNotIn(self.token, response.text)
        self.assertIn('type="password"', response.text)
        self.assertIn('script src="/dashboard/app.js"', response.text)
        script = self.client.get("/dashboard/app.js")
        self.assertEqual(script.status_code, 200)
        self.assertEqual(script.headers["cache-control"], "no-store")
        self.assertNotIn("localStorage", script.text)
        self.assertNotIn("sessionStorage", script.text)
        self.assertNotIn("innerHTML", script.text)
        self.assertIn("textContent", script.text)

    def test_dashboard_route_does_not_bypass_bearer_auth_or_scopes(self):
        self.assertEqual(self.client.get("/api/v1/records").status_code, 401)
        response = self.client.get(
            "/api/v1/records", headers={"Authorization": "Bearer " + self.token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [entry["id"] for entry in response.json()["records"]], ["allowed"])
        self.assertEqual(
            self.client.put("/api/v1/records/allowed/address",
                            headers={"Authorization": "Bearer " + self.token},
                            json={"address": "192.0.2.3", "request_id": "attempt"}).status_code,
            403)

    def test_remote_clients_denied_for_both_assets(self):
        for endpoint in (dashboard, dashboard_script):
            for host in ("203.0.113.42", "example.com", ""):
                with self.subTest(endpoint=endpoint.__name__, host=host):
                    request = SimpleNamespace(client=SimpleNamespace(host=host))
                    with self.assertRaises(HTTPException) as denied:
                        endpoint(request)
                    self.assertEqual(denied.exception.status_code, 403)
        for host in ("127.0.0.1", "::1"):
            require_loopback(SimpleNamespace(client=SimpleNamespace(host=host)))

    def test_assets_do_not_depend_on_login_state_or_network_services(self):
        self.assertIn("fetch(", SCRIPT)
        self.assertIn("/api/v1/records", SCRIPT)
        self.assertIn("/api/v1/intents/", SCRIPT)
        self.assertNotIn(self.token, PAGE)
        self.assertNotIn(self.token, SCRIPT)


if __name__ == "__main__":
    unittest.main()
