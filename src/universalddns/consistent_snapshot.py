"""Read one SQLite snapshot generation through a pinned file descriptor.

Not connected to broker. Requires publisher-controlled rollback-mode snapshots.
"""
import os
import sqlite3
import stat
import time
import uuid
from pathlib import Path

from .record_inventory import MAX_RECORDS

READ_DEADLINE_SECONDS = 1.0
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024


def read_consistent_snapshot(
    path: str | Path, *, trusted_producer_uid: int | None = None
) -> dict[str, object]:
    """Deserialize the same inode's bytes after an atomic destination replacement.

    Reading via the already-open descriptor avoids SQLite reopening a deleted
    pathname. Deserialization needs bounded memory; not for live databases.
    """
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != expected_uid or info.st_nlink != 1
                or not 100 <= info.st_size <= MAX_SNAPSHOT_BYTES):
            raise ValueError("snapshot unavailable")
        header = os.pread(fd, 20, 0)
        if header[:16] != b"SQLite format 3\x00" or header[18:20] != b"\x01\x01":
            raise ValueError("snapshot unavailable")
        deadline = time.monotonic() + READ_DEADLINE_SECONDS
        chunks = []
        remaining = info.st_size
        while remaining:
            if time.monotonic() >= deadline:
                raise ValueError("snapshot unavailable")
            block = os.read(fd, min(65536, remaining))
            if not block:
                raise ValueError("snapshot unavailable")
            chunks.append(block)
            remaining -= len(block)
        after = os.fstat(fd)
        if (time.monotonic() >= deadline or after.st_size != info.st_size
                or after.st_mtime_ns != info.st_mtime_ns
                or after.st_ctime_ns != info.st_ctime_ns):
            raise ValueError("snapshot unavailable")
        with sqlite3.connect(":memory:") as db:
            db.deserialize(b"".join(chunks))
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
    except (OSError, sqlite3.Error, ValueError, AttributeError) as exc:
        raise ValueError("snapshot unavailable") from exc
    finally:
        if fd is not None:
            os.close(fd)
