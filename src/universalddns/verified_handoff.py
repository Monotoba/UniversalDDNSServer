"""Fail-closed, non-issuing verification of a session-bound SCM_RIGHTS FD.

This helper does not authorize a publisher or issue registry trust.
"""
import os
import uuid
import time

from .consistent_snapshot import read_snapshot_fd
from .snapshot_handoff import HandoffSession, receive_snapshot_fd
from .peer_lifecycle import require_live_peer_pidfd


def receive_verified_snapshot(
    channel, *, authorized_uid: int, producer_uid: int,
    session: HandoffSession, expected_generation: str,
    authorized_pid: int | None = None,
    expected_identity: tuple[int, int] | None = None,
    peer_pidfd: int | None = None, deadline: float | None = None,
) -> dict[str, object]:
    """Consume one session, verify pinned bytes and return untrusted metadata.

    expected_generation must originate from an independently authorized
    publisher observation, not the transfer payload or sending peer alone.
    """
    if type(session) is not HandoffSession or session.consumed:
        raise ValueError("snapshot unavailable")
    # Failures before receipt also burn the one-shot challenge.
    if (type(expected_generation) is not str or len(expected_generation) != 32
            or (expected_identity is not None and
                (type(expected_identity) is not tuple
                 or len(expected_identity) != 2
                 or any(type(n) is not int or n < 0 for n in expected_identity)))):
        session.consumed = True
        raise ValueError("snapshot unavailable")
    try:
        generation = uuid.UUID(hex=expected_generation).hex
    except (ValueError, AttributeError) as exc:
        session.consumed = True
        raise ValueError("snapshot unavailable") from exc
    fd = None
    try:
        if deadline is not None and time.monotonic() >= deadline:
            raise ValueError("snapshot unavailable")
        if peer_pidfd is not None:
            require_live_peer_pidfd(
                channel, expected_pid=authorized_pid, pidfd=peer_pidfd)
        fd = receive_snapshot_fd(
            channel, authorized_uid=authorized_uid,
            producer_uid=producer_uid, authorized_pid=authorized_pid,
            session=session, deadline=deadline)
        before = os.fstat(fd)
        if expected_identity is not None and (
            before.st_dev, before.st_ino) != expected_identity:
            raise ValueError("snapshot unavailable")
        result = read_snapshot_fd(fd, trusted_producer_uid=producer_uid)
        after = os.fstat(fd)
        if ((before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                or after.st_nlink != 1 or result["generation"] != generation):
            raise ValueError("snapshot unavailable")
        if deadline is not None and time.monotonic() >= deadline:
            raise ValueError("snapshot unavailable")
        if peer_pidfd is not None:
            require_live_peer_pidfd(
                channel, expected_pid=authorized_pid, pidfd=peer_pidfd)
        if deadline is not None and time.monotonic() >= deadline:
            raise ValueError("snapshot unavailable")
        return result
    except (OSError, ValueError, TypeError) as exc:
        # Even if receive rejects credentials before consuming the session.
        session.consumed = True
        raise ValueError("snapshot unavailable") from exc
    finally:
        if fd is not None:
            os.close(fd)
