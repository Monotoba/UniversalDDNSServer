"""Isolated, fail-closed freshness gate; not wired to services or broker.

Trusted inputs must originate outside the snapshot from an authorized,
in-process publication observer. They must never come from a client or file.
"""
import math
import time
import uuid
from collections.abc import Mapping

MAX_TRUSTED_AGE_SECONDS = 300.0


def require_fresh_snapshot(
    snapshot: Mapping[str, object],
    *,
    trusted_generation: str,
    trusted_issued_monotonic: float,
    now_monotonic: float | None = None,
    max_age_seconds: float = MAX_TRUSTED_AGE_SECONDS,
) -> dict[str, object]:
    """Validate snapshot against a trusted same-boot, monotonic issuance record.

    This helper does NOT authenticate its arguments. Its caller must establish
    producer identity, issuance provenance and clock-domain continuity.
    """
    try:
        if type(trusted_generation) is not str or len(trusted_generation) != 32:
            raise ValueError("snapshot unavailable")
        uuid.UUID(hex=trusted_generation)
        if type(snapshot.get("generation")) is not str:
            raise ValueError("snapshot unavailable")
        if snapshot["generation"] != trusted_generation:
            raise ValueError("snapshot unavailable")
        if type(snapshot.get("created_at")) is not int:
            raise ValueError("snapshot unavailable")
        for value in (trusted_issued_monotonic, max_age_seconds):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("snapshot unavailable")
        if not 0 < max_age_seconds <= MAX_TRUSTED_AGE_SECONDS:
            raise ValueError("snapshot unavailable")
        current = time.monotonic() if now_monotonic is None else now_monotonic
        if type(current) not in (int, float) or not math.isfinite(current):
            raise ValueError("snapshot unavailable")
        age = current - trusted_issued_monotonic
        if not 0 <= age <= max_age_seconds:
            raise ValueError("snapshot unavailable")
        for field in ("total_records", "staged_active_records", "staged_inactive_records"):
            value = snapshot.get(field)
            if type(value) is not int or value < 0:
                raise ValueError("snapshot unavailable")
        if (snapshot["staged_active_records"] + snapshot["staged_inactive_records"]
                != snapshot["total_records"]):
            raise ValueError("snapshot unavailable")
        return dict(snapshot)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("snapshot unavailable") from exc
