"""Experimental Unix socket broker: authenticated ping only, no admin mutations.

Not installed as a service or wired into any CLI. A supervisor must supply the
already-bound listening socket and secure its path, ownership and mode.
"""
import socket

from .operator_peer import authenticated_operator_peer
from .operator_protocol import read_request, send_response


def handle_connection(connection: socket.socket) -> None:
    """Authenticate the OS peer before parsing any request contents."""
    try:
        operator = authenticated_operator_peer(connection)
    except PermissionError:
        return  # Refuse without echoing identity or reading attacker-controlled JSON.
    try:
        read_request(connection)
        send_response(connection, {"ok": True, "version": 1, "operator": operator})
    except (ValueError, OSError, TimeoutError):
        try:
            send_response(connection, {"ok": False, "error": "invalid request"})
        except OSError:
            pass
