"""Isolated supervised snapshot metadata verification; not connected to broker.

The parent exclusively owns issuance. A child reads untrusted SQLite bytes
and returns a bounded binary metadata frame, never Python objects.
"""
import multiprocessing
import os
import struct
import time
import uuid
from pathlib import Path

from .authorized_observer import _read_exact_until
from .consistent_snapshot import read_consistent_snapshot

_FRAME = struct.Struct("!4s16sqIII")
_MAGIC = b"UVRF"


def _verification_child(path: str, send) -> None:
    try:
        snapshot = read_consistent_snapshot(path)
        frame = _FRAME.pack(
            _MAGIC, uuid.UUID(hex=snapshot["generation"]).bytes,
            snapshot["created_at"], snapshot["total_records"],
            snapshot["staged_active_records"],
            snapshot["staged_inactive_records"],
        )
        send.send_bytes(frame)
    finally:
        send.close()


def verify_snapshot_supervised(
    path: str | Path, *, timeout_seconds: float = 2.0,
) -> dict[str, object]:
    """Bound one child verification attempt with a parent-enforced deadline.

    Only accepts a cleanly exited child and a fixed-size metadata frame.
    This does not authenticate an arbitrary publisher or preserve trust.
    """
    if (os.name != "posix" or not hasattr(os, "fork")
            or type(timeout_seconds) not in (int, float)
            or not 0 < timeout_seconds <= 30):
        raise ValueError("snapshot unavailable")
    deadline = time.monotonic() + timeout_seconds
    parent = child = process = None
    try:
        context = multiprocessing.get_context("fork")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(
            target=_verification_child, args=(os.fspath(path), child))
        process.start()
        child.close()
        child = None
        fd = parent.fileno()
        size = int.from_bytes(_read_exact_until(fd, 4, deadline),
                              "big", signed=True)
        if size != _FRAME.size:
            raise ValueError("snapshot unavailable")
        frame = _read_exact_until(fd, size, deadline)
        process.join(max(0, deadline - time.monotonic()))
        if process.is_alive() or process.exitcode != 0:
            raise ValueError("snapshot unavailable")
        if os.read(fd, 1) != b"":
            raise ValueError("snapshot unavailable")
        if time.monotonic() >= deadline:
            raise ValueError("snapshot unavailable")
        magic, generation, created, total, active, inactive = _FRAME.unpack(frame)
        if magic != _MAGIC or active + inactive != total:
            raise ValueError("snapshot unavailable")
        return {
            "generation": uuid.UUID(bytes=generation).hex,
            "created_at": created,
            "total_records": total,
            "staged_active_records": active,
            "staged_inactive_records": inactive,
        }
    except (OSError, EOFError, ValueError, TypeError, struct.error) as exc:
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
