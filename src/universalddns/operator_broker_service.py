"""Opt-in, ping-only systemd socket-activated broker.

Requires exactly one AF_UNIX SOCK_STREAM fd passed by systemd. This module does
not bind filesystem paths, touch SQLite, or access TSIG keys.
"""
import grp
import os
import pwd
import selectors
import socket
import stat
import sys
from threading import Event

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
    # systemd creates the parent root-owned; others need search permission
    # to reach a group-restricted socket without listing its directory.
    if not parent.st_mode & stat.S_IXOTH:
        raise RuntimeError("operator socket parent is not traversable")
    endpoint = os.lstat(OPERATOR_SOCKET_PATH)
    if not stat.S_ISSOCK(endpoint.st_mode):
        raise RuntimeError("operator endpoint must be a filesystem socket")
    if endpoint.st_mode & 0o007:
        raise RuntimeError("operator endpoint permissions are too broad")


def validate_endpoint_ownership() -> None:
    """Require the socket owner and group configured in the systemd socket unit."""
    try:
        expected_uid = pwd.getpwnam("universalddns").pw_uid
        expected_gid = grp.getgrnam("universalddns-operators").gr_gid
    except (KeyError, OSError) as exc:
        raise RuntimeError("operator socket account or group unavailable") from exc
    endpoint = os.lstat(OPERATOR_SOCKET_PATH)
    if not stat.S_ISSOCK(endpoint.st_mode):
        raise RuntimeError("operator endpoint must be a filesystem socket")
    if endpoint.st_uid != expected_uid or endpoint.st_gid != expected_gid:
        raise RuntimeError("operator socket ownership differs from systemd configuration")
    if stat.S_IMODE(endpoint.st_mode) != 0o660:
        raise RuntimeError("operator socket mode differs from systemd configuration")



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
        validate_endpoint_ownership()
        return candidate
    except BaseException:
        candidate.close()
        raise


def serve(listener: socket.socket, stop_event: Event | None = None) -> None:
    """Sequential handler; optional stop event supports isolated lifecycle tests."""
    with selectors.DefaultSelector() as selector:
        listener.setblocking(False)
        selector.register(listener, selectors.EVENT_READ)
        while True:
            if not selector.select(timeout=0.1 if stop_event is not None else None):
                if stop_event is not None and stop_event.is_set():
                    break
                continue
            if stop_event is not None and stop_event.is_set():
                break
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
