"""Validated backend-neutral A/AAAA DNS resource record sets."""
from dataclasses import dataclass
from ipaddress import ip_address
import re

_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

def canonical_name(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("invalid DNS name")
    name = value.lower().rstrip(".")
    if not name or len(name) > 253 or any(not _LABEL.fullmatch(s) for s in name.split(".")):
        raise ValueError("invalid DNS name")
    return name + "."

@dataclass(frozen=True, slots=True)
class RecordSet:
    zone: str
    name: str
    record_type: str
    ttl: int
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        zone = canonical_name(self.zone)
        name = canonical_name(self.name)
        if name != zone and not name.endswith("." + zone):
            raise ValueError("record name must be within zone")
        rt = self.record_type.upper()
        if rt not in ("A", "AAAA"):
            raise ValueError("only A and AAAA are implemented")
        if not isinstance(self.ttl, int) or isinstance(self.ttl, bool) or not 0 <= self.ttl <= 2147483647:
            raise ValueError("invalid TTL")
        if not isinstance(self.values, tuple) or not self.values:
            raise ValueError("RRset must contain at least one address")
        normalized = []
        for value in self.values:
            addr = ip_address(value)
            if addr.version != (4 if rt == "A" else 6):
                raise ValueError("IP family does not match record type")
            normalized.append(str(addr))
        if len(normalized) != len(set(normalized)):
            raise ValueError("duplicate addresses")
        object.__setattr__(self, "zone", zone)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "record_type", rt)
        object.__setattr__(self, "values", tuple(sorted(normalized)))

    @property
    def key(self) -> tuple[str, str, str]:
        return self.zone, self.name, self.record_type
