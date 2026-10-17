"""Volatile trusted issuance registry; isolated from publisher and broker.

Only an authorized in-process observer may record a successful publication.
State is deliberately lost on process restart; no serialized token is trusted.
"""
import os
import time
import uuid
from collections.abc import Mapping

from .snapshot_freshness import require_fresh_snapshot


class SnapshotIssuanceRegistry:
    """One-process, one-generation trust anchor; lost state fails closed."""

    def __init__(self) -> None:
        self._pid = os.getpid()
        self._epoch = uuid.uuid4().hex
        self._generation: str | None = None
        self._issued: float | None = None

    def issue(self, generation: str, *, observed_monotonic: float | None = None) -> None:
        """Record only AFTER successful publication; caller must authorize action."""
        if os.getpid() != self._pid:
            raise ValueError("snapshot unavailable")
        instant = time.monotonic() if observed_monotonic is None else observed_monotonic
        # Reuse the conservative validator to reject bad generations and clocks.
        marker = {"generation": generation, "created_at": 0,
                  "total_records": 0, "staged_active_records": 0,
                  "staged_inactive_records": 0}
        require_fresh_snapshot(
            marker, trusted_generation=generation,
            trusted_issued_monotonic=instant, now_monotonic=instant)
        if self._issued is not None and instant < self._issued:
            raise ValueError("snapshot unavailable")
        self._generation, self._issued = generation, instant

    def validate(self, snapshot: Mapping[str, object], *,
                 now_monotonic: float | None = None) -> dict[str, object]:
        """Require same PID, existing issuance state and matching generation."""
        if (os.getpid() != self._pid or self._generation is None
                or self._issued is None):
            raise ValueError("snapshot unavailable")
        return require_fresh_snapshot(
            snapshot, trusted_generation=self._generation,
            trusted_issued_monotonic=self._issued,
            now_monotonic=now_monotonic)

    def invalidate(self) -> None:
        """Fail closed after publisher uncertainty or shutdown."""
        if os.getpid() != self._pid:
            raise ValueError("snapshot unavailable")
        self._generation = None
        self._issued = None
