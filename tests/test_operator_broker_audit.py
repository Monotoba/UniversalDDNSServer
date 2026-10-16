"""Structured broker audit events exclude rejected peer claims and request payloads."""
import socket
import unittest
from unittest.mock import patch

from universalddns.operator_broker import handle_connection


class BrokerAuditTests(unittest.TestCase):
    def test_successful_ping_audits_kernel_identity(self):
        with socket.socketpair() as (server, client):
            client.sendall(b'{"version":1,"operation":"ping"}\n')
            with patch("universalddns.operator_broker.authenticated_operator_peer",
                       return_value="authorized"), \
                 patch("universalddns.operator_broker.audit") as audit:
                handle_connection(server)
            self.assertIn(b'"ok":true', client.recv(1024))
            audit.assert_called_once_with("operator_ping_succeeded",
                                          operator="authorized")

    def test_invalid_request_audits_without_payload(self):
        with socket.socketpair() as (server, client):
            client.sendall(b'{"token":"secret","operation":"write"}\n')
            with patch("universalddns.operator_broker.authenticated_operator_peer",
                       return_value="authorized"), \
                 patch("universalddns.operator_broker.audit") as audit:
                handle_connection(server)
            self.assertIn(b'"ok":false', client.recv(1024))
            audit.assert_called_once_with("operator_request_rejected",
                                          operator="authorized")

    def test_unauthorized_peer_audits_without_identity_or_read(self):
        with socket.socketpair() as (server, client):
            with patch("universalddns.operator_broker.authenticated_operator_peer",
                       side_effect=PermissionError("untrusted secret identity")), \
                 patch("universalddns.operator_broker.read_request") as read, \
                 patch("universalddns.operator_broker.audit") as audit:
                handle_connection(server)
            read.assert_not_called()
            audit.assert_called_once_with("operator_peer_rejected")

    def test_broken_response_not_misreported_as_success(self):
        with socket.socketpair() as (server, client):
            with patch("universalddns.operator_broker.authenticated_operator_peer",
                       return_value="authorized"), \
                 patch("universalddns.operator_broker.read_request"), \
                 patch("universalddns.operator_broker.send_response",
                       side_effect=BrokenPipeError), \
                 patch("universalddns.operator_broker.audit") as audit:
                handle_connection(server)
            audit.assert_called_once_with("operator_request_rejected",
                                          operator="authorized")


if __name__ == "__main__":
    unittest.main()
