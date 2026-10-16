"""Opt-in, ping-only systemd socket-activated broker.

Requires exactly one AF_UNIX SOCK_STREAM fd passed by systemd. This module does
not bind filesystem paths, touch SQLite, or access TSIG keys.
"""
import os
import selectors
import socket
import stat
import sys

from .operator_broker import handle_connection


def inherited_listener() -> socket.socket:
    """Validate systemd's exact single-fd activation contract, failing closed."""
    if os.name != "posix":
        raise RuntimeError("POSIX required")
    if os.environ.get("LISTEN_PID") != str(os.getpid()):
        raise RuntimeError("not activated by this process")
    if os.environ.get("LISTEN_FDS") != "1":
        raise RuntimeError("exactly one inherited socket required")
    if os.environ.get("LISTEN_FDNAMES") not in (None, "operator"):
        raise RuntimeError("unexpected socket name")
    mode = os.fstat(3).st_mode
    if not stat.S_ISSOCK(mode):
        raise RuntimeError("inherited fd is not a socket")
    # Duplicate first: failed validation must not close systemd's original fd.
    candidate = socket.fromfd(3, socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        if candidate.family != socket.AF_UNIX or candidate.type & socket.SOCK_STREAM != socket.SOCK_STREAM:
            raise RuntimeError("AF_UNIX stream listener required")
        if candidate.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) != 1:
            raise RuntimeError("socket is not listening")
        path = candidate.getsockname()
        if not isinstance(path, str) or not path.startswith("/run/universalddns/"):
            raise RuntimeError("unexpected Unix socket path")
        return candidate
    except BaseException:
        candidate.close()
        raise


def serve(listener: socket.socket) -> None:
    """Sequential bounded handler; shutdown follows SIGTERM via default action."""
    with selectors.DefaultSelector() as selector:
        listener.setblocking(False)
        selector.register(listener, selectors.EVENT_READ)
        while True:
            selector.select()
            try:
                connection, _ = listener.accept()
            except BlockingIOError:
                continue
            with connection:
                handle_connection(connection)


def main() -> int:
    try:
        with inherited_listener() as listener:
            serve(listener)
    except (OSError, RuntimeError) as exc:
        print(f"operator broker cannot start: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
