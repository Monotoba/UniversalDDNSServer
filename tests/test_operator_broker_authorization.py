"""Ensure unauthenticated Unix peers cannot send requests to the broker."""
import socket
from contextlib import ExitStack
import unittest
from unittest.mock import patch

from universalddns.operator_broker import handle_connection


class BrokerUnauthorizedPeerTests(unittest.TestCase):
    def test_refused_peer_has_no_request_parsed_or_response(self):
        with ExitStack() as stack:
            server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
            stack.enter_context(server)
            stack.enter_context(client)
            with patch("universalddns.operator_broker.authenticated_operator_peer",
                       side_effect=PermissionError("not an operator")), \
                 patch("universalddns.operator_broker.read_request") as read, \
                 patch("universalddns.operator_broker.send_response") as send:
                handle_connection(server)
            read.assert_not_called()
            send.assert_not_called()
            client.settimeout(0.1)
            with self.assertRaises(TimeoutError):
                client.recv(1)


if __name__ == "__main__":
    unittest.main()
