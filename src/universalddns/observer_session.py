"""Cooperative observer-session fencing in disposable private directories.

Only participants using this observer protocol are coordinated. Direct
snapshot publishers bypass this lock; this is not a production trust boundary.
"""
import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator

from .authorized_observer import (
    publish_with_authorized_child, read_current_authorized_snapshot,
)
from .snapshot_issuance import SnapshotIssuanceRegistry


@contextmanager
def observer_session(destination: str | Path) -> Iterator[None]:
    """Hold a pinned, persistent nonblocking flock across observer operation."""
    target = Path(destination)
    parent = target.parent
    fd = None
    directory = None
    try:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("snapshot unavailable")
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        current = os.fstat(directory)
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("snapshot unavailable")
        fd = os.open(".inventory-observer.lock",
                     os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600,
                     dir_fd=directory)
        lock = os.fstat(fd)
        if (not stat.S_ISREG(lock.st_mode) or stat.S_IMODE(lock.st_mode) != 0o600
                or lock.st_uid != os.geteuid() or lock.st_nlink != 1):
            raise ValueError("snapshot unavailable")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except (OSError, BlockingIOError, ValueError) as exc:
        raise ValueError("snapshot unavailable") from exc
    finally:
        if fd is not None:
            os.close(fd)
        if directory is not None:
            os.close(directory)


def publish_in_observer_session(
    source: str | Path, destination: str | Path,
    registry: SnapshotIssuanceRegistry, *, timeout_seconds: float = 10.0,
    descriptor_handoff: bool = False,
) -> dict[str, object]:
    """Serialize cooperative publication and acknowledgement across processes."""
    with observer_session(destination):
        return publish_with_authorized_child(
            source, destination, registry, timeout_seconds=timeout_seconds,
            descriptor_handoff=descriptor_handoff)


def read_in_observer_session(
    destination: str | Path, registry: SnapshotIssuanceRegistry,
) -> dict[str, object]:
    """Serialize a cooperative current-generation read with those publications."""
    with observer_session(destination):
        return read_current_authorized_snapshot(destination, registry)
