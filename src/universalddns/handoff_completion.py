"""Optional bounded two-way completion handshake for isolated snapshot handoffs.

Session state and trust issuance remain parent-controlled; these frames are
not independently authenticated publication or durable issuance evidence.
"""
import socket
import time

from .peer_lifecycle import require_live_peer_pidfd
from .snapshot_handoff import HandoffSession, HANDOFF_TIMEOUT_SECONDS
from .verified_handoff import receive_verified_snapshot


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ValueError("snapshot unavailable")
    return remaining


def _read_exact(channel: socket.socket, count: int, deadline: float | None = None) -> bytes:
    data = bytearray()
    while len(data) < count:
        if deadline is not None:
            channel.settimeout(min(HANDOFF_TIMEOUT_SECONDS, _remaining(deadline)))
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
    peer_pidfd: int, deadline: float | None = None,
) -> dict[str, object]:
    """Verify FD, then require an exact one-shot echo from the live sender."""
    if type(session) is not HandoffSession or session.consumed:
        raise ValueError("snapshot unavailable")
    try:
        if deadline is not None:
            if type(deadline) not in (int, float):
                raise ValueError("snapshot unavailable")
            channel.settimeout(min(HANDOFF_TIMEOUT_SECONDS, _remaining(deadline)))
        data = receive_verified_snapshot(
            channel, authorized_uid=authorized_uid,
            producer_uid=producer_uid, authorized_pid=authorized_pid,
            session=session, expected_generation=expected_generation,
            expected_identity=expected_identity, peer_pidfd=peer_pidfd,
            deadline=deadline)
        if deadline is not None:
            channel.settimeout(min(HANDOFF_TIMEOUT_SECONDS, _remaining(deadline)))
        else:
            channel.settimeout(HANDOFF_TIMEOUT_SECONDS)
        channel.sendall(b"V" + session.challenge)
        if _read_exact(channel, 33, deadline) != b"A" + session.challenge:
            raise ValueError("snapshot unavailable")
        # Reject bytes already queued beyond the one permitted completion frame.
        # A later write remains a protocol violation not provable at this instant.
        if channel.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT):
            raise ValueError("snapshot unavailable")
        if deadline is not None:
            _remaining(deadline)
        require_live_peer_pidfd(
            channel, expected_pid=authorized_pid, pidfd=peer_pidfd)
        if deadline is not None:
            _remaining(deadline)
        return data
    except (OSError, ValueError, TypeError) as exc:
        session.consumed = True
        raise ValueError("snapshot unavailable") from exc
