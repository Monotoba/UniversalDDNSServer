"""Optional bounded two-way completion handshake for isolated snapshot handoffs.

Session state and trust issuance remain parent-controlled; these frames are
not independently authenticated publication or durable issuance evidence.
"""
import os
import socket

from .peer_lifecycle import require_live_peer_pidfd
from .snapshot_handoff import HandoffSession, HANDOFF_TIMEOUT_SECONDS
from .verified_handoff import receive_verified_snapshot


def _read_exact(channel: socket.socket, count: int) -> bytes:
    data = bytearray()
    while len(data) < count:
        block = channel.recv(count - len(data))
        if not block:
            raise ValueError("snapshot unavailable")
        data.extend(block)
    return bytes(data)


def acknowledge_verified_handoff(
    channel: socket.socket, *, challenge: bytes,
) -> None:
    """Sender remains alive to echo the parent's post-verification frame."""
    if type(challenge) is not bytes or len(challenge) != 32:
        raise ValueError("snapshot unavailable")
    try:
        channel.settimeout(HANDOFF_TIMEOUT_SECONDS)
        frame = _read_exact(channel, 33)
        if frame != b"V" + challenge:
            raise ValueError("snapshot unavailable")
        channel.sendall(b"A" + challenge)
    except (OSError, ValueError) as exc:
        raise ValueError("snapshot unavailable") from exc


def receive_completed_snapshot(
    channel: socket.socket, *, authorized_uid: int, producer_uid: int,
    authorized_pid: int, session: HandoffSession,
    expected_generation: str, expected_identity: tuple[int, int],
    peer_pidfd: int,
) -> dict[str, object]:
    """Verify FD, then require an exact one-shot echo from the live sender."""
    if type(session) is not HandoffSession or session.consumed:
        raise ValueError("snapshot unavailable")
    try:
        data = receive_verified_snapshot(
            channel, authorized_uid=authorized_uid,
            producer_uid=producer_uid, authorized_pid=authorized_pid,
            session=session, expected_generation=expected_generation,
            expected_identity=expected_identity, peer_pidfd=peer_pidfd)
        channel.settimeout(HANDOFF_TIMEOUT_SECONDS)
        channel.sendall(b"V" + session.challenge)
        if _read_exact(channel, 33) != b"A" + session.challenge:
            raise ValueError("snapshot unavailable")
        require_live_peer_pidfd(
            channel, expected_pid=authorized_pid, pidfd=peer_pidfd)
        return data
    except (OSError, ValueError, TypeError) as exc:
        session.consumed = True
        raise ValueError("snapshot unavailable") from exc
