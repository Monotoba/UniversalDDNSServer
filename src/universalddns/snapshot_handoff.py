"""Isolated Linux SCM_RIGHTS snapshot descriptor handoff primitives.

No listening socket, broker command, service or deployment integration.
Caller must authenticate the peer before sending any descriptor.
"""
import array
import os
import socket
import stat
import struct
from pathlib import Path

_MAX_MESSAGE = 1
_CREDENTIALS = struct.Struct("3i")


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
    channel: socket.socket, snapshot: str | Path, *, authorized_uid: int
) -> None:
    """Send one validated read-only snapshot fd to the authorized peer."""
    if type(authorized_uid) is not int or authorized_uid < 0:
        raise ValueError("handoff unavailable")
    if peer_credentials(channel)[1] != authorized_uid:
        raise ValueError("handoff unavailable")
    fd = None
    try:
        fd = os.open(snapshot, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.geteuid() or info.st_nlink != 1):
            raise ValueError("handoff unavailable")
        rights = array.array("i", [fd])
        sent = channel.sendmsg([b"S"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS,
                                          rights.tobytes())])
        if sent != 1:
            raise ValueError("handoff unavailable")
    except OSError as exc:
        raise ValueError("handoff unavailable") from exc
    finally:
        if fd is not None:
            os.close(fd)


def receive_snapshot_fd(
    channel: socket.socket, *, authorized_uid: int, producer_uid: int
) -> int:
    """Receive exactly one read-only descriptor, caller must close result.

    A returned fd is not a trusted snapshot: a consumer must still inspect
    its contents, expected generation and freshness before using counts.
    """
    if (type(authorized_uid) is not int or authorized_uid < 0
            or type(producer_uid) is not int or producer_uid < 0):
        raise ValueError("handoff unavailable")
    if peer_credentials(channel)[1] != authorized_uid:
        raise ValueError("handoff unavailable")
    incoming = array.array("i")
    try:
        payload, controls, flags, _ = channel.recvmsg(
            _MAX_MESSAGE, socket.CMSG_SPACE(4 * incoming.itemsize)
        )
        received = []
        for level, kind, data in controls:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                count = len(data) // incoming.itemsize
                received.extend(struct.unpack(f"{count}i", data[:count * incoming.itemsize]))
        try:
            if flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC) or payload != b"S" or len(received) != 1:
                raise ValueError("handoff unavailable")
            fd = received[0]
            info = os.fstat(fd)
            access = __import__("fcntl").fcntl(fd, __import__("fcntl").F_GETFL)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != producer_uid
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                    or access & os.O_ACCMODE != os.O_RDONLY):
                raise ValueError("handoff unavailable")
            received.clear()
            os.set_inheritable(fd, False)
            return fd
        finally:
            for fd in received:
                os.close(fd)
    except OSError as exc:
        raise ValueError("handoff unavailable") from exc
