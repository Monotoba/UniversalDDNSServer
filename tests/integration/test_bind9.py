"""Ephemeral local BIND 9 integration; never queries or changes public DNS."""
import base64
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
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
