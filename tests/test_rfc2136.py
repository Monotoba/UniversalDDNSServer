import unittest
from unittest.mock import Mock
import dns.message
import dns.opcode
import dns.rcode
import dns.rdatatype
from universalddns.domain import RecordSet
from universalddns.adapters.rfc2136 import RFC2136Backend, RFC2136Config, DNSPublicationError

KEY = "c2VjcmV0c2VjcmV0"  # Public dummy secret for tests only.

class RFC2136Tests(unittest.TestCase):
    def setUp(self):
        self.config = RFC2136Config("example.org", "127.0.0.1", "ddns-key.", KEY)
        self.rr = RecordSet("example.org", "host.example.org", "A", 120, ("192.0.2.1", "192.0.2.2"))

    def test_builds_signed_dns_update_tcp(self):
        captured = []
        def transport(message, where, **kwargs):
            captured.append((message, where, kwargs))
            return dns.message.make_response(message)
        backend = RFC2136Backend(self.config, transport=transport)
        backend.publish(self.rr)
        message, where, kwargs = captured[0]
        self.assertEqual(message.opcode(), dns.opcode.UPDATE)
        self.assertEqual(where, "127.0.0.1")
        self.assertEqual(kwargs["port"], 53)
        self.assertTrue(message.had_tsig)
        self.assertEqual(len(message.authority), 3)
        self.assertEqual(message.authority[1].rdtype, dns.rdatatype.A)

    def test_rejects_cross_zone_before_network(self):
        mock = Mock()
        backend = RFC2136Backend(self.config, transport=mock)
        with self.assertRaises(ValueError):
            backend.publish(RecordSet("other.org", "host.other.org", "A", 120, ("192.0.2.1",)))
        mock.assert_not_called()

    def test_server_rejects(self):
        def transport(message, *_args, **_kwargs):
            result = dns.message.make_response(message)
            result.set_rcode(dns.rcode.REFUSED)
            return result
        with self.assertRaisesRegex(DNSPublicationError, "REFUSED"):
            RFC2136Backend(self.config, transport=transport).publish(self.rr)

    def test_timeout_redacts_secret(self):
        def transport(*_args, **_kwargs):
            raise OSError("secret from transport")
        with self.assertRaises(DNSPublicationError) as context:
            RFC2136Backend(self.config, transport=transport).publish(self.rr)
        self.assertNotIn("secret from transport", str(context.exception))

    def test_config_validation(self):
        for server in ("example.org", "", "127.0.0.1;bad"):
            with self.subTest(server=server), self.assertRaises(ValueError):
                RFC2136Config("example.org", server, "key", KEY)
        with self.assertRaises(ValueError):
            RFC2136Config("example.org", "127.0.0.1", "key", KEY, key_algorithm="hmac-md5")
        with self.assertRaises(ValueError):
            RFC2136Config("example.org", "127.0.0.1", "key", "not base64")
