"""RFC 2136 DNS UPDATE adapter with TSIG authentication.

Acknowledgment from a DNS backend does not prove cache convergence.
"""
import base64
import binascii
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Callable

import dns.exception
import dns.query
import dns.rcode
import dns.tsigkeyring
import dns.update

from ..domain import RecordSet, canonical_name
from ..ports import BackendCapabilities


class DNSPublicationError(RuntimeError):
    """The authoritative server rejected or could not process an update."""


@dataclass(frozen=True, slots=True)
class RFC2136Config:
    zone: str
    server: str
    key_name: str
    key_secret: str
    key_algorithm: str = "hmac-sha256"
    port: int = 53
    timeout: float = 5.0

    def __post_init__(self):
        object.__setattr__(self, "zone", canonical_name(self.zone))
        if not self.server or not isinstance(self.server, str):
            raise ValueError("server required")
        # Do not allow client-controlled DNS names for the update destination.
        ip_address(self.server)
        if not self.key_name or not self.key_secret:
            raise ValueError("TSIG key name and secret required")
        try:
            if not base64.b64decode(self.key_secret, validate=True):
                raise ValueError("empty TSIG secret")
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid TSIG secret encoding") from exc
        if not 1 <= self.port <= 65535 or not 0 < self.timeout <= 60:
            raise ValueError("invalid port or timeout")
        if self.key_algorithm not in ("hmac-sha256", "hmac-sha384", "hmac-sha512"):
            raise ValueError("unsupported TSIG algorithm")


class RFC2136Backend:
    """Replace an A/AAAA RRset using signed DNS UPDATE over TCP."""

    capabilities = BackendCapabilities(frozenset({"A", "AAAA"}), supports_prerequisites=False)

    def __init__(self, config: RFC2136Config, *, transport: Callable | None = None):
        self._config = config
        self._keyring = dns.tsigkeyring.from_text({config.key_name: config.key_secret})
        self._transport = transport or dns.query.tcp

    def publish(self, rrset: RecordSet) -> None:
        if rrset.zone != self._config.zone:
            raise ValueError("RRset is outside configured backend zone")
        if rrset.record_type not in self.capabilities.supported_record_types:
            raise ValueError("unsupported DNS record type")
        update = dns.update.Update(
            self._config.zone,
            keyring=self._keyring,
            keyname=self._config.key_name,
            keyalgorithm=self._config.key_algorithm,
        )
        # Replaces the entire RRset; tightly scoped TSIG server policy is essential.
        update.replace(rrset.name, rrset.ttl, rrset.record_type, *rrset.values)
        try:
            response = self._transport(update, self._config.server, port=self._config.port,
                                       timeout=self._config.timeout)
        except (dns.exception.DNSException, OSError) as exc:
            raise DNSPublicationError("DNS update transport failed") from exc
        if response.rcode() != dns.rcode.NOERROR:
            raise DNSPublicationError(f"DNS update rejected: {dns.rcode.to_text(response.rcode())}")
