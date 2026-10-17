"""Isolated authorized-child publication observation fixture; not a service API.

The parent launches exactly one publisher child and retains issuance authority.
A private multiprocessing Pipe is not a general cross-process authentication
protocol; only the parent-created child is authorized in this fixture.
"""
import multiprocessing
import os
import secrets
import select
import stat
import time
import threading
from pathlib import Path

from .ack_frame import FRAME_BYTES, decode_ack, encode_ack
from .consistent_snapshot import read_consistent_snapshot
from .inventory_snapshot import publish_inventory_snapshot
from .snapshot_issuance import SnapshotIssuanceRegistry

_observer_lock = threading.Lock()


def _read_exact_until(fd: int, count: int, deadline: float) -> bytes:
    """Bounded raw-pipe read; never deserialize or wait past the deadline."""
    data = bytearray()
    while len(data) < count:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("snapshot unavailable")
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            raise ValueError("snapshot unavailable")
        chunk = os.read(fd, count - len(data))
        if not chunk:
            raise ValueError("snapshot unavailable")
        data.extend(chunk)
    return bytes(data)


def _read_bounded_ack(connection, deadline: float) -> bytes:
    """Read the Connection wire length before the fixed-size binary frame."""
    fd = connection.fileno()
    length = int.from_bytes(_read_exact_until(fd, 4, deadline), "big", signed=True)
    if length != FRAME_BYTES:
        raise ValueError("snapshot unavailable")
    return _read_exact_until(fd, FRAME_BYTES, deadline)



def _publisher_child(source: str, destination: str, connection, nonce: str) -> None:
    try:
        def acknowledged(generation: str) -> None:
            connection.send_bytes(encode_ack(nonce, generation))

        publish_inventory_snapshot(
            source, destination, on_durable_publication=acknowledged)
    finally:
        connection.close()


def publish_with_authorized_child(
    source: str | Path, destination: str | Path,
    registry: SnapshotIssuanceRegistry, *, timeout_seconds: float = 10.0,
) -> dict[str, object]:
    """Issue only after a known child succeeds and bytes match its acknowledgement.

    Linux fork-based proof-of-concept. Does not prevent another process from
    replacing the snapshot after this check. The directory must have a single
    authorized writer for that stronger guarantee.
    """
    if os.name != "posix" or not hasattr(os, "fork"):
        raise ValueError("snapshot unavailable")
    if type(timeout_seconds) not in (float, int) or not 0 < timeout_seconds <= 30:
        raise ValueError("snapshot unavailable")
    if not _observer_lock.acquire(blocking=False):
        raise ValueError("snapshot unavailable")
    parent = child = process = None
    succeeded = False
    try:
        registry.invalidate()
        context = multiprocessing.get_context("fork")
        parent, child = context.Pipe(duplex=False)
        nonce = secrets.token_hex(32)
        process = context.Process(
            target=_publisher_child,
            args=(os.fspath(source), os.fspath(destination), child, nonce))
        process.start()
        child.close()
        child = None
        deadline = time.monotonic() + timeout_seconds
        message = _read_bounded_ack(parent, deadline)
        process.join(max(0, deadline - time.monotonic()))
        if process.is_alive() or process.exitcode != 0:
            raise ValueError("snapshot unavailable")
        generation = decode_ack(message, nonce)
        # After clean child exit, EOF is mandatory; trailing bytes are refused.
        if os.read(parent.fileno(), 1) != b"":
            raise ValueError("snapshot unavailable")
        snapshot = read_consistent_snapshot(destination)
        if snapshot["generation"] != generation:
            raise ValueError("snapshot unavailable")
        registry.issue(generation)
        validated = read_current_authorized_snapshot(destination, registry)
        succeeded = True
        return validated
    except (OSError, EOFError, ValueError, TypeError) as exc:
        raise ValueError("snapshot unavailable") from exc
    finally:
        if process is not None:
            if process.is_alive():
                process.kill()
            process.join()
        if child is not None:
            child.close()
        if parent is not None:
            parent.close()
        if not succeeded:
            registry.invalidate()
        _observer_lock.release()


def read_current_authorized_snapshot(
    destination: str | Path, registry: SnapshotIssuanceRegistry,
) -> dict[str, object]:
    """Validate the *current* path against trusted issuance, not a cached read.

    Reject replacement during this observation by comparing the current inode
    before and after the pinned-FD reader. This is not a durable lease: a
    separate publisher may replace the path immediately after return.
    """
    target = Path(destination)
    try:
        before = target.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("snapshot unavailable")
        snapshot = read_consistent_snapshot(target)
        validated = registry.validate(snapshot)
        after = target.lstat()
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError("snapshot unavailable")
        return validated
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("snapshot unavailable") from exc
