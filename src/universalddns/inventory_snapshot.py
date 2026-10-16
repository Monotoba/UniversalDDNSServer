"""Isolated SQLite snapshot producer; not wired to the broker or services."""
import os
import fcntl
import hashlib
import uuid
import sqlite3
import stat
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from .record_inventory import read_record_inventory

SNAPSHOT_MAX_AGE_SECONDS = 300
BACKUP_DEADLINE_SECONDS = 5.0


def snapshot_fingerprint(path: str | Path) -> str:
    """Content integrity fingerprint; authenticity still requires a trusted publisher."""
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_snapshot_generation(path: str | Path) -> tuple[str, int]:
    """Read internal generation metadata; not proof of authenticity or trust."""
    try:
        with sqlite3.connect(f"file:{quote(os.path.abspath(os.fspath(path)), safe='/')}?mode=ro", uri=True) as db:
            rows = db.execute("SELECT generation, created_at FROM inventory_generation").fetchall()
        if (len(rows) != 1 or not isinstance(rows[0][0], str)
                or len(rows[0][0]) != 32 or not isinstance(rows[0][1], int)):
            raise ValueError("snapshot unavailable")
        uuid.UUID(hex=rows[0][0])
        return rows[0]
    except (sqlite3.Error, OSError, ValueError) as exc:
        raise ValueError("snapshot unavailable") from exc


def snapshot_is_fresh(path: str | Path, *, now: float | None = None) -> bool:
    """Conservative freshness check; does not assert snapshot trust or ownership."""
    try:
        age = (time.time() if now is None else now) - Path(path).stat().st_mtime
    except OSError:
        return False
    return 0 <= age <= SNAPSHOT_MAX_AGE_SECONDS




def _clean_abandoned_staging(directory_fd: int) -> None:
    """Remove only validated orphan staging files while publisher lock is held.

    Operates through the pinned directory descriptor to avoid path replacement.
    Never removes the published snapshot or persistent lock inode.
    """
    for name in os.listdir(directory_fd):
        if not (name.startswith(".inventory-") and name.endswith(".sqlite3")):
            continue
        details = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (not stat.S_ISREG(details.st_mode)
                or details.st_uid != os.geteuid()
                or stat.S_IMODE(details.st_mode) != 0o600
                or details.st_nlink != 1):
            raise ValueError("snapshot unavailable")
        os.unlink(name, dir_fd=directory_fd)

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
        lock_info = os.fstat(lock_fd)
        if (not stat.S_ISREG(lock_info.st_mode)
                or stat.S_IMODE(lock_info.st_mode) != 0o600
                or lock_info.st_uid != os.geteuid()
                or lock_info.st_nlink != 1):
            raise ValueError("snapshot unavailable")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("snapshot unavailable") from exc
        _clean_abandoned_staging(directory_fd)
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
                # Metadata and records live in the SAME atomic SQLite file.
                copy.execute("CREATE TABLE inventory_generation (generation TEXT NOT NULL, created_at INTEGER NOT NULL)")
                copy.execute("INSERT INTO inventory_generation VALUES (?, ?)",
                             (uuid.uuid4().hex, int(time.time())))
        counts = read_record_inventory(temp)
        read_snapshot_generation(temp)
        # Compute a deterministic fingerprint for a future trusted manifest.
        # Do not treat a bare digest or filesystem mtime as authentication.
        snapshot_fingerprint(temp)
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
            try:
                os.unlink(temp.name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        if lock_fd is not None:
            os.close(lock_fd)
        os.close(directory_fd)
