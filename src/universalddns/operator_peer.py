"""Linux Unix-socket peer authentication primitive for a future local admin broker.

Not wired into the existing CLI. Never accept a client-supplied identity.
"""
import grp
import os
import pwd
import socket
import struct


def authenticated_operator_peer(connection: socket.socket) -> str:
    """Return an authorized non-root OS username derived from SO_PEERCRED.

    This helper authenticates identity at connection time. The broker must still
    constrain socket ownership, request framing, allowed operations, and auditing.
    """
    if os.name != "posix" or not hasattr(socket, "SO_PEERCRED"):
        raise PermissionError("Linux peer credentials required")
    if connection.family != socket.AF_UNIX:
        raise PermissionError("Unix-domain socket required")
    data = connection.getsockopt(
        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
    )
    pid, uid, gid = struct.unpack("3i", data)
    if pid <= 0 or uid <= 0 or gid < 0:
        raise PermissionError("privileged or unidentified socket peer")
    try:
        identity = pwd.getpwuid(uid)
        group = grp.getgrnam("universalddns-operators")
        groups = os.getgrouplist(identity.pw_name, identity.pw_gid)
    except (KeyError, OSError) as exc:
        raise PermissionError("socket peer or operator group unavailable") from exc
    username = identity.pw_name
    if (
        not username or len(username) > 128 or not username.isascii()
        or any(not (ch.isalnum() or ch in "-_.") for ch in username)
    ):
        raise PermissionError("unsupported socket peer identity")
    if group.gr_gid not in groups:
        raise PermissionError("socket peer is not an authorized operator")
    return username
