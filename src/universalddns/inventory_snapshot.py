"""Isolated SQLite snapshot producer; not wired to the broker or services."""
import os
import sqlite3
import tempfile
import time
from pathlib import Path

from .record_inventory import read_record_inventory

SNAPSHOT_MAX_AGE_SECONDS = 300


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
    mode = parent.stat().st_mode
    if not parent.is_dir() or mode & 0o077:
        raise ValueError("snapshot unavailable")
    if target.is_symlink():
        raise ValueError("snapshot unavailable")
    fd, temp_name = tempfile.mkstemp(prefix=".inventory-", suffix=".sqlite3", dir=parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        os.chmod(temp, 0o600)
        uri = "file:" + __import__("urllib.parse", fromlist=["quote"]).quote(
            os.path.abspath(os.fspath(source)), safe="/"
        ) + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=0.2) as live:
            with sqlite3.connect(temp) as copy:
                live.backup(copy, pages=64, sleep=0.01)
                journal = copy.execute("PRAGMA journal_mode=DELETE").fetchone()
                if journal != ("delete",):
                    raise ValueError("snapshot unavailable")
        counts = read_record_inventory(temp)
        with temp.open("rb") as f:
            os.fsync(f.fileno())
        os.replace(temp, target)
        directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return counts
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise ValueError("snapshot unavailable") from exc
    finally:
        temp.unlink(missing_ok=True)
