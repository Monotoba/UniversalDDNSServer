"""Isolated Linux SCM_RIGHTS snapshot descriptor handoff primitives.

No listening socket, broker command, service or deployment integration.
Caller must authenticate the peer before sending any descriptor.
"""
import array
import fcntl
import os
import secrets
import socket
import stat
import struct
from pathlib import Path

_MAX_MESSAGE = 33
HANDOFF_TIMEOUT_SECONDS = 2.0
_CREDENTIALS = struct.Struct("3i")


class HandoffSession:
    """Single-use receiver challenge. Never reuse after success or failure."""

    def __init__(self):
        self.challenge = secrets.token_bytes(32)
        self.consumed = False


def peer_credentials(channel: socket.socket) -> tuple[int, int, int]:
    """Return kernel-verified (pid, uid, gid) for a connected Unix socket."""
    try:
        if channel.family != socket.AF_UNIX:
            raise ValueError("handoff unavailable")
        raw = channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                 _CREDENTIALS.size)
        return _CREDENTIALS.unpack(raw)
    except (OSError, struct.error) as exc:
        raise ValueError("handoff unavailable") from exc


def send_snapshot_fd(
    channel: socket.socket, snapshot: str | Path, *, authorized_uid: int,
    authorized_pid: int | None = None, session_challenge: bytes | None = None,
) -> None:
    """Send one validated read-only snapshot fd to the authorized peer."""
    if (type(authorized_uid) is not int or authorized_uid < 0
            or (authorized_pid is not None and
                (type(authorized_pid) is not int or authorized_pid <= 0))):
        raise ValueError("handoff unavailable")
    pid, uid, _ = peer_credentials(channel)
    if uid != authorized_uid or (authorized_pid is not None and pid != authorized_pid):
        raise ValueError("handoff unavailable")
    if (session_challenge is not None and
            (type(session_challenge) is not bytes or len(session_challenge) != 32)):
        raise ValueError("handoff unavailable")
    fd = None
    try:
        channel.settimeout(HANDOFF_TIMEOUT_SECONDS)
        fd = os.open(snapshot, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.geteuid() or info.st_nlink != 1):
            raise ValueError("handoff unavailable")
        rights = array.array("i", [fd])
        sent = channel.sendmsg([b"S" + (session_challenge or b"")], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                          rights.tobytes())])
        if sent != 1 + (32 if session_challenge is not None else 0):
            raise ValueError("handoff unavailable")
    except OSError as exc:
        raise ValueError("handoff unavailable") from exc
    finally:
        if fd is not None:
            os.close(fd)


def receive_snapshot_fd(
    channel: socket.socket, *, authorized_uid: int, producer_uid: int,
    authorized_pid: int | None = None, session: HandoffSession | None = None,
) -> int:
    """Receive exactly one read-only descriptor, caller must close result.

    A returned fd is not a trusted snapshot: a consumer must still inspect
    its contents, expected generation and freshness before using counts.
    """
    if (type(authorized_uid) is not int or authorized_uid < 0
            or type(producer_uid) is not int or producer_uid < 0
            or (authorized_pid is not None and
                (type(authorized_pid) is not int or authorized_pid <= 0))):
        raise ValueError("handoff unavailable")
    pid, uid, _ = peer_credentials(channel)
    if uid != authorized_uid or (authorized_pid is not None and pid != authorized_pid):
        raise ValueError("handoff unavailable")
    if session is not None:
        if type(session) is not HandoffSession or session.consumed:
            raise ValueError("handoff unavailable")
        session.consumed = True
    incoming = array.array("i")
    try:
        channel.settimeout(HANDOFF_TIMEOUT_SECONDS)
        payload, controls, flags, _ = channel.recvmsg(
            _MAX_MESSAGE, socket.CMSG_SPACE(4 * incoming.itemsize)
        )
        received = []
        try:
            for level, kind, data in controls:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    count = len(data) // incoming.itemsize
                    received.extend(struct.unpack(f"{count}i", data[:count * incoming.itemsize]))
            expected = b"S" if session is None else b"S" + session.challenge
            if flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC) or payload != expected or len(received) != 1:
                raise ValueError("handoff unavailable")
            fd = received[0]
            info = os.fstat(fd)
            access = fcntl.fcntl(fd, fcntl.F_GETFL)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != producer_uid
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                    or access & os.O_ACCMODE != os.O_RDONLY):
                raise ValueError("handoff unavailable")
            os.set_inheritable(fd, False)
            received.clear()
            return fd
        finally:
            for fd in received:
                os.close(fd)
    except OSError as exc:
        raise ValueError("handoff unavailable") from exc
