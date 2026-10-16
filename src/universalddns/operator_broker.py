"""Experimental Unix socket broker: authenticated ping only, no admin mutations.

Not installed as a service or wired into any CLI. A supervisor must supply the
already-bound listening socket and secure its path, ownership and mode.
"""
import socket

from .audit import audit
from .operator_peer import authenticated_operator_peer
from .operator_protocol import read_request, send_response


def handle_connection(connection: socket.socket) -> None:
    """Authenticate the OS peer before parsing any request contents."""
    try:
        operator = authenticated_operator_peer(connection)
    except PermissionError:
        # Do not log attacker-controlled request contents or claimed identity.
        audit("operator_peer_rejected")
        return
    try:
        read_request(connection)
        send_response(connection, {"ok": True, "version": 1, "operator": operator})
    except (ValueError, OSError, TimeoutError):
        audit("operator_request_rejected", operator=operator)
        try:
            send_response(connection, {"ok": False, "error": "invalid request"})
        except OSError:
            pass
    else:
        audit("operator_ping_succeeded", operator=operator)
