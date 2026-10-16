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

OPERATOR_SOCKET_PATH = "/run/universalddns/operator.sock"
OPERATOR_SOCKET_DIRECTORY = "/run/universalddns"


def validate_endpoint_filesystem() -> None:
    """Reject path substitution and writable runtime-directory boundaries."""
    parent = os.lstat(OPERATOR_SOCKET_DIRECTORY)
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0:
        raise RuntimeError("operator socket parent must be a root-owned directory")
    if parent.st_mode & 0o022:
        raise RuntimeError("operator socket parent must not be group/other writable")
    # systemd creates the parent root-owned; others need search permission\n    # to reach a group-restricted socket without listing its directory.\n    if not parent.st_mode & stat.S_IXOTH:\n        raise RuntimeError("operator socket parent is not traversable")\n    endpoint = os.lstat(OPERATOR_SOCKET_PATH)
    if not stat.S_ISSOCK(endpoint.st_mode):
        raise RuntimeError("operator endpoint must be a filesystem socket")
    if endpoint.st_mode & 0o007:
        raise RuntimeError("operator endpoint permissions are too broad")



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
        if path != OPERATOR_SOCKET_PATH:
            raise RuntimeError("unexpected Unix socket path")
        validate_endpoint_filesystem()
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
