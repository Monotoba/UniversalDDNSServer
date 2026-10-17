"""Isolated authorized-child publication observation fixture; not a service API.

The parent launches exactly one publisher child and retains issuance authority.
A private multiprocessing Pipe is not a general cross-process authentication
protocol; only the parent-created child is authorized in this fixture.
"""
import multiprocessing
import os
import secrets
import stat
import threading
from pathlib import Path

from .consistent_snapshot import read_consistent_snapshot
from .inventory_snapshot import publish_inventory_snapshot
from .snapshot_issuance import SnapshotIssuanceRegistry

_observer_lock = threading.Lock()


def _publisher_child(source: str, destination: str, connection, nonce: str) -> None:
    try:
        def acknowledged(generation: str) -> None:
            connection.send((nonce, generation))

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
        if not parent.poll(timeout_seconds):
            raise ValueError("snapshot unavailable")
        message = parent.recv()
        process.join(timeout_seconds)
        if process.is_alive() or process.exitcode != 0:
            raise ValueError("snapshot unavailable")
        if (type(message) is not tuple or len(message) != 2
                or type(message[0]) is not str or message[0] != nonce
                or type(message[1]) is not str):
            raise ValueError("snapshot unavailable")
        generation = message[1]
        if parent.poll(0):
            try:
                parent.recv()
            except EOFError:
                pass  # Closed writer is normal; a second payload is not.
            else:
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
