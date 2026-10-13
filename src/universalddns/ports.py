"""Core-owned replaceable interfaces (version 1)."""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from .domain import RecordSet

CORE_PORT_API_VERSION = 1

@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    supported_record_types: frozenset[str]
    supports_prerequisites: bool = False

@runtime_checkable
class RecordRepository(Protocol):
    def get(self, zone: str, name: str, record_type: str) -> RecordSet | None: ...
    def put(self, rrset: RecordSet) -> bool: ...
    def delete(self, zone: str, name: str, record_type: str) -> bool: ...
    def close(self) -> None: ...

@runtime_checkable
class DNSBackend(Protocol):
    @property
    def capabilities(self) -> BackendCapabilities: ...
    def publish(self, rrset: RecordSet) -> None: ...

@runtime_checkable
class Authorizer(Protocol):
    def may_update(self, principal_id: str, rrset: RecordSet) -> bool: ...

@runtime_checkable
class EventSink(Protocol):
    def record(self, kind: str, rrset: RecordSet) -> None: ...
