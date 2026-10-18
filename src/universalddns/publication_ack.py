"""Isolated, in-process durable-publication to volatile-issuance adapter."""
import threading
from pathlib import Path

from .inventory_snapshot import publish_inventory_snapshot
from .snapshot_issuance import SnapshotIssuanceRegistry


_ack_lock = threading.Lock()


def publish_and_acknowledge(
    source: str | Path, destination: str | Path, registry: SnapshotIssuanceRegistry
) -> dict[str, int]:
    """Fail closed before publication and on any failed acknowledgement.

    For a single authorized publisher process; not safe as an uncoordinated
    multi-threaded observer or an authenticated cross-process protocol.
    """
    # Nonblocking serialization avoids invalidation by an overlapping attempt.
    if not _ack_lock.acquire(blocking=False):
        raise ValueError("snapshot unavailable")
    try:
        registry.invalidate()
        try:
            return publish_inventory_snapshot(
                source, destination, on_durable_publication=registry.issue
            )
        except BaseException:
            registry.invalidate()
            raise
    finally:
        _ack_lock.release()
