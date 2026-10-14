"""Structured audit logging emits bounded JSON and excludes sensitive input."""
import json
import logging
import unittest

from universalddns.audit import audit


class AuditTests(unittest.TestCase):
    def test_structured_event(self):
        with self.assertLogs("universalddns.audit", logging.INFO) as captured:
            audit("publication_applied", intent="1234-abcd", principal="local_user")
        data = json.loads(captured.records[0].getMessage())
        self.assertEqual(data, {
            "event": "publication_applied",
            "intent": "1234-abcd",
            "principal": "local_user",
        })

    def test_sensitive_values_are_redacted(self):
        with self.assertLogs("universalddns.audit", logging.INFO) as captured:
            audit("authentication_denied", reason="Bearer secret with whitespace")
        self.assertEqual(json.loads(captured.records[0].getMessage())["reason"],
                         "[redacted]")
        self.assertNotIn("secret", captured.records[0].getMessage())

    def test_invalid_key_and_event_rejected(self):
        with self.assertRaises(ValueError):
            audit("invalid event")
        with self.assertRaises(ValueError):
            audit("authentication_denied", **{"token secret": "unsafe"})


if __name__ == "__main__":
    unittest.main()
