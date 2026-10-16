"""Read one immutable SQLite snapshot generation through a pinned file descriptor.

Not connected to the broker. Requires publisher-controlled files and directory.
"""
import os
import sqlite3
import stat
import time
import uuid
from pathlib import Path

from .record_inventory import MAX_RECORDS

READ_DEADLINE_SECONDS = 1.0


def read_consistent_snapshot(path: str | Path) -> dict[str, object]:
    """Keep the same inode for metadata and counts across atomic replacement.

    Linux-specific /proc/self/fd URI. Only safe for publisher-controlled,
    rollback-mode standalone snapshots, never a changing live DB.
    """
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
            raise ValueError("snapshot unavailable")
        if os.pread(fd, 20, 0)[:16] != b"SQLite format 3\x00":
            raise ValueError("snapshot unavailable")
        if os.pread(fd, 2, 18) != b"\x01\x01":
            raise ValueError("snapshot unavailable")
        deadline = time.monotonic() + READ_DEADLINE_SECONDS
        # The file descriptor remains open while SQLite reads that same inode.
        with sqlite3.connect(f"file:/proc/self/fd/{fd}?mode=ro&immutable=1",
                             uri=True, timeout=0.2) as db:
            db.execute("PRAGMA query_only=ON")
            db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
            row = db.execute(
                "SELECT generation, created_at FROM inventory_generation"
            ).fetchall()
            counts = db.execute(
                "SELECT COUNT(*), SUM(CASE WHEN active=1 THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN active=0 THEN 1 ELSE 0 END) FROM managed_records"
            ).fetchone()
        if time.monotonic() >= deadline or len(row) != 1 or counts is None:
            raise ValueError("snapshot unavailable")
        generation, created_at = row[0]
        if (type(generation) is not str or len(generation) != 32
                or type(created_at) is not int):
            raise ValueError("snapshot unavailable")
        uuid.UUID(hex=generation)
        total, active, inactive = counts
        active = 0 if active is None else active
        inactive = 0 if inactive is None else inactive
        if (any(type(v) is not int or not 0 <= v <= MAX_RECORDS
                for v in (total, active, inactive))
                or active + inactive != total):
            raise ValueError("snapshot unavailable")
        return {"generation": generation, "created_at": created_at,
                "total_records": total, "staged_active_records": active,
                "staged_inactive_records": inactive}
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise ValueError("snapshot unavailable") from exc
    finally:
        if fd is not None:
            os.close(fd)
