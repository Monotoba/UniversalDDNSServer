"""Opt-in isolated authorized publication descriptor-check stage; no service IPC."""
import multiprocessing
import os
import socket
import stat
import time
import uuid
from pathlib import Path

from .snapshot_handoff import HandoffSession, send_snapshot_fd
from .verified_handoff import receive_verified_snapshot


def _handoff_sender(address: str, destination: str, challenge: bytes,
                    parent_pid: int) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(2.0)
        connection.connect(address)
        send_snapshot_fd(connection, destination, authorized_uid=os.geteuid(),
                         authorized_pid=parent_pid, session_challenge=challenge)


def verify_authorized_handoff(destination: str | Path, generation: str,
                              deadline: float) -> dict[str, object]:
    """Require exact parent-created sender PID, challenge, inode and generation.

    Independent trust issuance MUST occur outside this helper after success.
    """
    process = None
    session = HandoffSession()
    target = Path(destination)
    try:
        before = target.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("snapshot unavailable")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("snapshot unavailable")
        address = "\x00uddns-verified-" + uuid.uuid4().hex
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(address)
            listener.listen(1)
            listener.settimeout(min(remaining, 2.0))
            ctx = multiprocessing.get_context("fork")
            process = ctx.Process(target=_handoff_sender, args=(
                address, os.fspath(target), session.challenge, os.getpid()))
            process.start()
            with listener.accept()[0] as channel:
                channel.settimeout(max(0.001, deadline - time.monotonic()))
                result = receive_verified_snapshot(
                    channel, authorized_uid=os.geteuid(),
                    producer_uid=os.geteuid(), authorized_pid=process.pid,
                    session=session, expected_generation=generation,
                    expected_identity=(before.st_dev, before.st_ino))
            process.join(max(0, deadline - time.monotonic()))
            if process.is_alive() or process.exitcode != 0:
                raise ValueError("snapshot unavailable")
            after = target.lstat()
            if ((after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
                    or time.monotonic() >= deadline):
                raise ValueError("snapshot unavailable")
            return result
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("snapshot unavailable") from exc
    finally:
        session.consumed = True
        if process is not None:
            if process.is_alive():
                process.kill()
            process.join()
