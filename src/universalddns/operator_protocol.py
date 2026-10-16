"""Bounded, versioned local administrative protocol; no write operations yet."""
import json
import socket
import time

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 4096
MAX_RESPONSE_BYTES = 4096
SOCKET_TIMEOUT = 2.0


def read_request(connection: socket.socket) -> dict[str, object]:
    """Accept exactly one newline-terminated JSON object, with a strict schema."""
    deadline = time.monotonic() + SOCKET_TIMEOUT
    payload = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("request deadline exceeded")
        connection.settimeout(remaining)
        chunk = connection.recv(min(1024, MAX_REQUEST_BYTES + 1 - len(payload)))
        if not chunk:
            raise ValueError("incomplete request")
        payload.extend(chunk)
        if len(payload) > MAX_REQUEST_BYTES:
            raise ValueError("request too large")
        if b"\n" in chunk:
            if payload.count(b"\n") != 1 or not payload.endswith(b"\n"):
                raise ValueError("multiple or trailing requests refused")
            break
    try:
        request = json.loads(payload[:-1])
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON") from exc
    if (
        type(request) is not dict
        or set(request) != {"version", "operation"}
        or type(request["version"]) is not int
        or request["version"] != PROTOCOL_VERSION
        or request["operation"] != "ping"
    ):
        raise ValueError("unsupported operation or protocol")
    return request


def send_response(connection: socket.socket, result: dict[str, object]) -> None:
    """Send exactly one bounded result, never arbitrary user-supplied payloads."""
    data = (json.dumps(result, separators=(",", ":"), sort_keys=True) + "\n").encode()
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("response too large")
    # A peer that stops reading must not hold the sequential broker indefinitely.\n    # Python socket sendall uses this timeout as a total send budget.\n    connection.settimeout(SOCKET_TIMEOUT)\n    connection.sendall(data)
