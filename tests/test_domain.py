import unittest
from universalddns.domain import RecordSet, canonical_name

class DomainTests(unittest.TestCase):
    def test_normalization(self):
        r = RecordSet("Example.com", "EDGE.example.com.", "aaaa", 300, ("2001:0DB8::1",))
        self.assertEqual(r.key, ("example.com.", "edge.example.com.", "AAAA"))
        self.assertEqual(r.values, ("2001:db8::1",))
    def test_invalid_addresses(self):
        with self.assertRaises(ValueError):
            RecordSet("example.com", "h.example.com", "A", 60, ("::1",))
    def test_zone_scope(self):
        with self.assertRaises(ValueError):
            RecordSet("example.com", "evil-example.com", "A", 60, ("192.0.2.1",))
    def test_hostnames(self):
        for bad in ("", "*.example", "a..example", "-a.example", " "):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                canonical_name(bad)
    def test_duplicates_and_ttl(self):
        with self.assertRaises(ValueError):
            RecordSet("example.com","a.example.com","A",60,("192.0.2.1","192.0.2.1"))
        with self.assertRaises(ValueError):
            RecordSet("example.com","a.example.com","A",-1,("192.0.2.1",))
    def test_future_record_type_not_enabled(self):
        with self.assertRaises(ValueError):
            RecordSet("example.com","a.example.com","TXT",60,("value",))
