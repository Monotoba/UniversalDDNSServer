"""Isolated SQLite snapshot producer; not wired to the broker or services."""
import os
import fcntl
import sqlite3
import stat
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from .record_inventory import read_record_inventory

SNAPSHOT_MAX_AGE_SECONDS = 300
BACKUP_DEADLINE_SECONDS = 5.0


def snapshot_is_fresh(path: str | Path, *, now: float | None = None) -> bool:
    """Conservative freshness check; does not assert snapshot trust or ownership."""
    try:
        age = (time.time() if now is None else now) - Path(path).stat().st_mtime
    except OSError:
        return False
    return 0 <= age <= SNAPSHOT_MAX_AGE_SECONDS


def publish_inventory_snapshot(source: str | Path, destination: str | Path) -> dict[str, int]:
    """Back up SQLite to an atomically replaced private standalone DB.

    Paths are trusted configuration, never client input. Caller must provision
    an owner-controlled private directory and authorize source database access.
    """
    target = Path(destination)
    parent = target.parent
    try:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
            raise ValueError("snapshot unavailable")
        if target.is_symlink():
            raise ValueError("snapshot unavailable")
        # Pin directory identity across staging and final publication.
        directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ValueError("snapshot unavailable") from exc
    if os.fstat(directory_fd).st_ino != info.st_ino or os.fstat(directory_fd).st_dev != info.st_dev:
        os.close(directory_fd)
        raise ValueError("snapshot unavailable")
    lock_fd = None
    try:
        # The lock inode persists; never unlink it (avoids split-brain locks).
        lock_fd = os.open(".inventory-publish.lock",
                          os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600,
                          dir_fd=directory_fd)
        if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
            raise ValueError("snapshot unavailable")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("snapshot unavailable") from exc
        fd, temp_name = tempfile.mkstemp(prefix=".inventory-", suffix=".sqlite3", dir=parent)
        os.close(fd)
        temp = Path(temp_name)
        os.chmod(temp, 0o600)
        uri = "file:" + quote(
            os.path.abspath(os.fspath(source)), safe="/"
        ) + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=0.2) as live:
            with sqlite3.connect(temp) as copy:
                deadline = time.monotonic() + BACKUP_DEADLINE_SECONDS

                def backup_progress(status: int, remaining: int, total: int) -> None:
                    if time.monotonic() >= deadline:
                        raise ValueError("snapshot unavailable")

                live.backup(copy, pages=64, sleep=0.01, progress=backup_progress)
                if time.monotonic() >= deadline:
                    raise ValueError("snapshot unavailable")
                journal = copy.execute("PRAGMA journal_mode=DELETE").fetchone()
                if journal != ("delete",):
                    raise ValueError("snapshot unavailable")
        counts = read_record_inventory(temp)
        with temp.open("rb") as f:
            os.fsync(f.fileno())
        # Refuse directory substitution and destination symlink races.
        if os.stat(parent, follow_symlinks=False).st_ino != info.st_ino:
            raise ValueError("snapshot unavailable")
        if target.is_symlink():
            raise ValueError("snapshot unavailable")
        os.replace(temp.name, target.name, src_dir_fd=directory_fd,
                   dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
        return counts
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise ValueError("snapshot unavailable") from exc
    finally:
        if 'temp' in locals():
            temp.unlink(missing_ok=True)
        if lock_fd is not None:
            os.close(lock_fd)
        os.close(directory_fd)
