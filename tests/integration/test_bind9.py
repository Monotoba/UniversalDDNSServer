"""Ephemeral local BIND 9 integration; never queries or changes public DNS."""
import base64
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from fastapi.testclient import TestClient
from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.http_api import create_app
from universalddns.orchestrator import UpdateOrchestrator
from universalddns.token_store import TokenStore
from universalddns.worker import PublicationWorker
from pathlib import Path

import dns.message
import dns.query
import dns.rcode

from universalddns.adapters.rfc2136 import RFC2136Backend, RFC2136Config
from universalddns.domain import RecordSet


@unittest.skipUnless(shutil.which(os.environ.get("DDNS_NAMED_BIN", "named")), "BIND 9 named executable required")
class Bind9IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.secret = base64.b64encode(b"ci-bind9-integration-key-not-for-production").decode()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]
        (root / "zone").write_text(
            '$TTL 60\n@ IN SOA ns.example.test. hostmaster.example.test. (1 3600 600 604800 60)\n'
            '@ IN NS ns.example.test.\nns IN A 127.0.0.1\n', encoding="utf-8"
        )
        conf = root / "named.conf"
        conf.write_text(
            f'options {{ directory "{root}"; listen-on port {cls.port} {{127.0.0.1;}}; '
            'listen-on-v6 { none; }; recursion no; allow-query {127.0.0.1;}; '
            f'pid-file "{root}/named.pid"; }};\n'
            f'key "ddns-key." {{ algorithm hmac-sha256; secret "{cls.secret}"; }};\n'
            'zone "example.test" { type primary; file "zone"; '
            'update-policy { grant ddns-key. zonesub A AAAA; }; };\n',
            encoding="utf-8",
        )
        cls.named_log = (root / "named.log").open("w+", encoding="utf-8")
        cls.proc = subprocess.Popen(
            [os.environ.get("DDNS_NAMED_BIN", "named"), "-g", "-c", str(conf), "-p", str(cls.port)],
            stdout=cls.named_log, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(60):
                if cls.proc.poll() is not None:
                    cls.named_log.flush()
                    raise RuntimeError("isolated named exited: " + (root / "named.log").read_text()[-4000:])
                try:
                    response = dns.query.tcp(
                        dns.message.make_query("example.test", "SOA"),
                        "127.0.0.1", port=cls.port, timeout=0.2,
                    )
                    if response.rcode() == dns.rcode.NOERROR:
                        break
                except Exception:
                    time.sleep(0.1)
            else:
                raise RuntimeError("isolated named did not become ready")
        except BaseException:
            cls.proc.terminate()
            cls.proc.wait(timeout=5)
            cls.tmp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
            cls.proc.wait(timeout=5)
        cls.tmp.cleanup()

    def backend(self, secret=None):
        return RFC2136Backend(RFC2136Config(
            "example.test", "127.0.0.1", "ddns-key.",
            secret if secret is not None else self.secret, port=self.port,
        ))

    def test_signed_a_and_aaaa_updates_and_authoritative_read(self):
        backend = self.backend()
        for record_type, values in (
            ("A", ("192.0.2.10", "192.0.2.11")),
            ("AAAA", ("2001:db8::10",)),
        ):
            with self.subTest(record_type=record_type):
                expected = RecordSet("example.test", "node.example.test",
                                     record_type, 120, values)
                backend.publish(expected)
                observed = backend.observe(expected)
                self.assertEqual(observed, expected)
        replacement = RecordSet("example.test", "node.example.test",
                                "A", 120, ("192.0.2.15",))
        backend.publish(replacement)
        self.assertEqual(backend.observe(replacement), replacement)

    def test_atomic_create_only_does_not_overwrite_existing_rrset(self):
        backend = self.backend()
        original = RecordSet("example.test", "onlyonce.example.test", "A",
                             120, ("192.0.2.30",))
        overwrite = RecordSet("example.test", "onlyonce.example.test", "A",
                              120, ("192.0.2.31",))
        backend.publish_if_absent(original)
        with self.assertRaises(Exception):
            backend.publish_if_absent(overwrite)
        self.assertEqual(backend.observe(original), original)

    def test_existing_record_prerequisite_rejects_stale_data(self):
        backend = self.backend()
        original = RecordSet("example.test", "condition.example.test",
                             "A", 120, ("192.0.2.41",))
        changed = RecordSet("example.test", "condition.example.test",
                            "A", 120, ("192.0.2.42",))
        stale = RecordSet("example.test", "condition.example.test",
                          "A", 120, ("192.0.2.43",))
        backend.publish(original)
        backend.publish_if_contains(original, changed)
        self.assertEqual(backend.observe(changed), changed)
        with self.assertRaises(Exception):
            backend.publish_if_contains(original, stale)
        self.assertEqual(backend.observe(changed), changed)


    def test_authenticated_http_queue_worker_to_authoritative_bind(self):
        class Allow:
            def may_update(self, principal_id, rrset):
                return principal_id == "device"

        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.db"
            record = RecordSet("example.test", "pipeline.example.test",
                               "A", 120, ("192.0.2.50",))
            with TokenStore(db) as store:
                token = store.issue("device", frozenset({"records:write", "intents:read"}),
                                    frozenset({"pipeline"}))
            def principal_provider():
                with TokenStore(db) as store:
                    return store.principals()
            def journal_factory():
                return SQLiteIntentJournal(db)
            def orchestrator_factory(journal):
                return UpdateOrchestrator(Allow(), journal, self.backend())
            app = create_app(journal_factory, orchestrator_factory,
                             {"pipeline": record}, principal_provider)
            with TestClient(app) as client:
                headers = {"Authorization": "Bearer " + token}
                result = client.put("/api/v1/records/pipeline/address",
                                    headers=headers,
                                    json={"address": "192.0.2.51",
                                          "request_id": "bind-pipeline-1"})
                self.assertEqual(result.status_code, 202)
                desired = RecordSet("example.test", "pipeline.example.test",
                                    "A", 120, ("192.0.2.51",))
                self.assertIsNone(self.backend().observe(desired))
                with journal_factory() as journal:
                    report = PublicationWorker(
                        journal, orchestrator_factory(journal)
                    ).run_once()
                    self.assertEqual(report.applied, 1)
                    self.assertEqual(PublicationWorker(
                        journal, orchestrator_factory(journal)
                    ).run_once().attempted, 0)
                self.assertEqual(self.backend().observe(desired), desired)
                status = client.get("/api/v1/intents/" + result.json()["intent_id"],
                                    headers=headers)
                self.assertEqual(status.json()["status"], "applied")
                with TokenStore(db) as store:
                    self.assertTrue(store.revoke(token))
                self.assertEqual(client.get(
                    "/api/v1/intents/" + result.json()["intent_id"],
                    headers=headers).status_code, 401)


    def test_uddnsupdater_client_to_real_bind_pipeline(self):
        """Cross-repository protocol test with HTTP transport bridged to ASGI.

        The client and server are real code; only HTTP transport is in-process.
        The authoritative DNS server is a real isolated named process.
        """
        import importlib
        import sys
        from unittest.mock import patch
        from uuid import uuid4

        client_source = os.environ.get("UDDNS_UPDATER_SOURCE")
        if not client_source:
            self.skipTest("UDDNS_UPDATER_SOURCE checkout not configured")
        sys.path.insert(0, client_source)
        try:
            provider_module = importlib.import_module("providers.provider_universalddns")
            provider_class = provider_module.UniversalDDNSServer
            with tempfile.TemporaryDirectory() as directory:
                db = Path(directory) / "state.db"
                name = "client-" + uuid4().hex[:10] + ".example.test"
                template = RecordSet("example.test", name, "A", 120, ("192.0.2.91",))
                desired = RecordSet("example.test", name, "A", 120, ("192.0.2.92",))
                with TokenStore(db) as store:
                    token = store.issue(
                        "updater", frozenset({"records:write", "intents:read"}),
                        frozenset({"client"}),
                    )

                class Allow:
                    def may_update(self, principal_id, rrset):
                        return principal_id == "updater"

                def journal_factory():
                    return SQLiteIntentJournal(db)

                def orchestrator_factory(journal):
                    return UpdateOrchestrator(Allow(), journal, self.backend())

                def principals():
                    with TokenStore(db) as store:
                        return store.principals()

                app = create_app(journal_factory, orchestrator_factory,
                                 {"client": template}, principals)
                calls = []

                with TestClient(app) as http:
                    def transport(session, method, url, **kwargs):
                        calls.append((method.upper(), url))
                        if url == "https://api.ipify.org":
                            # The updater's discovery is external to the DDNS
                            # system; stub only the discovered public IPv4.
                            class Discovery:
                                status_code = 200
                                text = "192.0.2.92"
                                def close(self):
                                    pass
                            return Discovery()
                        from urllib.parse import urlsplit
                        route = urlsplit(url).path
                        request = http.request(method.upper(), route,
                                               headers=kwargs.get("headers"),
                                               json=kwargs.get("json"))
                        class Reply:
                            status_code = request.status_code
                            text = request.text
                            def close(self):
                                pass
                        # Simulate a separate publishing process immediately
                        # after durable acceptance, before the first poll.
                        if method.upper() == "PUT" and request.status_code == 202:
                            with journal_factory() as journal:
                                report = PublicationWorker(
                                    journal, orchestrator_factory(journal)).run_once()
                                self.assertEqual(report.applied, 1)
                        return Reply()

                    with patch("requests.sessions.Session.request", transport):
                        provider = provider_class(
                            "local", {"base_url": "http://127.0.0.1:8765",
                                      "record_id": "client", "token": token})
                        self.assertTrue(provider.update_ddns())

                self.assertEqual(self.backend().observe(desired), desired)
                self.assertEqual([method for method, _ in calls],
                                 ["GET", "PUT", "GET"])
        finally:
            sys.path.remove(client_source)

    def test_wrong_tsig_is_rejected(self):
        bad = self.backend(base64.b64encode(b"wrong-key").decode())
        record = RecordSet("example.test", "denied.example.test",
                           "A", 120, ("192.0.2.16",))
        with self.assertRaises(Exception):
            bad.publish(record)
        self.assertIsNone(self.backend().observe(record))

    def test_cross_zone_rejected_before_update(self):
        record = RecordSet("other.test", "node.other.test",
                           "A", 60, ("192.0.2.5",))
        with self.assertRaises(ValueError):
            self.backend().publish(record)
