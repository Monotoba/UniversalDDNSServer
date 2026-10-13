"""Durable publishing intents and typed outcomes. No live DNS integration yet."""
from dataclasses import dataclass
from enum import StrEnum
from .domain import RecordSet

class UpdateState(StrEnum):
    PENDING = "pending"
    APPLYING = "applying"
    APPLIED = "applied"
    FAILED = "failed"

class UpdateError(Exception):
    """Base error for update orchestration."""

class PermissionDenied(UpdateError):
    """Principal is not allowed to modify the requested record."""

class UpdateConflict(UpdateError):
    """A different unfinished intent already owns this RRset."""

class UnknownIntent(UpdateError):
    """Intent identifier was not found."""

@dataclass(frozen=True, slots=True)
class UpdateIntent:
    identifier: str
    principal_id: str
    rrset: RecordSet
    state: UpdateState
    error: str | None = None
