"""Bounds and strict-schema checks for the experimental local broker protocol."""
import json
import socket
import unittest
from unittest.mock import Mock, patch

from universalddns.operator_broker import handle_connection
from universalddns.operator_protocol import read_request, send_response


class OperatorProtocolTests(unittest.TestCase):
    def read(self, request):
        a, b = socket.socketpair()
        try:
            b.sendall(request)
            return read_request(a)
        finally:
            a.close()
            b.close()

    def test_ping_only(self):
        self.assertEqual(self.read(b'{"version":1,"operation":"ping"}\n'),
                         {"version": 1, "operation": "ping"})

    def test_reject_mutation_and_identity_override(self):
        for data in (
            b'{"version":1,"operation":"issue"}\n',
            b'{"version":1,"operation":"ping","operator":"root"}\n',
            b'{"version":true,"operation":"ping"}\n',
            b'{"version":2,"operation":"ping"}\n',
            b'{"version":1,"operation":"ping"}\n{"version":1,"operation":"ping"}\n',
            b'x' * 4097 + b'\n',
        ):
            with self.subTest(request=data[:40]):
                with self.assertRaises(ValueError):
                    self.read(data)

    def test_reject_incomplete_request(self):
        a, b = socket.socketpair()
        try:
            b.sendall(b'{"version":1')
            b.shutdown(socket.SHUT_WR)
            with self.assertRaises(ValueError):
                read_request(a)
        finally:
            a.close()
            b.close()

    def test_authenticated_broker_ping(self):
        a, b = socket.socketpair()
        a.settimeout(3.0)
        b.settimeout(3.0)
        try:
            with patch("universalddns.operator_broker.authenticated_operator_peer",
                       return_value="test-operator"):
                b.sendall(b'{"version":1,"operation":"ping"}\n')
                handle_connection(a)
                data = b.recv(1024)
            self.assertEqual(json.loads(data), {
                "ok": True, "operator": "test-operator", "version": 1
            })
        finally:
            a.close()
            b.close()

    def test_auth_failure_does_not_read_client_payload(self):
        a, b = socket.socketpair()
        try:
            with patch("universalddns.operator_broker.authenticated_operator_peer",
                       side_effect=PermissionError("denied")):
                with patch("universalddns.operator_broker.read_request") as reader:
                    handle_connection(a)
                    reader.assert_not_called()
        finally:
            a.close()
            b.close()

    def test_response_write_is_bounded_even_without_prior_read(self):
        conn = Mock()
        send_response(conn, {"ok": True})
        conn.settimeout.assert_called_once_with(2.0)
        conn.sendall.assert_called_once()
        self.assertTrue(conn.sendall.call_args.args[0].endswith(b"\\n"))

    def test_response_timeout_propagates(self):
        conn = Mock()
        conn.sendall.side_effect = TimeoutError("client not reading")
        with self.assertRaises(TimeoutError):
            send_response(conn, {"ok": True})
        conn.settimeout.assert_called_once_with(2.0)

    def test_response_limit(self):
        a, b = socket.socketpair()
        try:
            with self.assertRaisesRegex(ValueError, "response too large"):
                send_response(a, {"data": "x" * 5000})
        finally:
            a.close()
            b.close()


if __name__ == "__main__":
    unittest.main()
