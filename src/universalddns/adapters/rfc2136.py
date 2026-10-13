"""RFC 2136 DNS UPDATE with TSIG; authoritative reads for reconciliation."""
import base64
import binascii
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Callable

import dns.exception
import dns.flags
import dns.message
import dns.query
import dns.rcode
import dns.rdatatype
import dns.tsigkeyring
import dns.update

from ..domain import RecordSet, canonical_name
from ..ports import BackendCapabilities


class DNSPublicationError(RuntimeError):
    """Authoritative DNS rejected a request or its result is unknown."""


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
        if not isinstance(self.server, str) or not self.server:
            raise ValueError("server required")
        ip_address(self.server)
        if not self.key_name or not self.key_secret:
            raise ValueError("TSIG key and secret required")
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
    capabilities = BackendCapabilities(frozenset({"A", "AAAA"}), supports_prerequisites=True)

    def __init__(self, config: RFC2136Config, *, transport: Callable | None = None):
        self._config = config
        self._keyring = dns.tsigkeyring.from_text({config.key_name: config.key_secret})
        self._transport = transport or dns.query.tcp

    def publish(self, rrset: RecordSet) -> None:
        if rrset.zone != self._config.zone:
            raise ValueError("RRset is outside configured backend zone")
        update = dns.update.Update(
            self._config.zone, keyring=self._keyring,
            keyname=self._config.key_name, keyalgorithm=self._config.key_algorithm,
        )
        update.replace(rrset.name, rrset.ttl, rrset.record_type, *rrset.values)
        try:
            response = self._transport(update, self._config.server,
                                       port=self._config.port, timeout=self._config.timeout)
        except (dns.exception.DNSException, OSError) as exc:
            raise DNSPublicationError("DNS update transport failed") from exc
        if response.rcode() != dns.rcode.NOERROR:
            raise DNSPublicationError(f"DNS update rejected: {dns.rcode.to_text(response.rcode())}")

    def publish_if_absent(self, rrset: RecordSet) -> None:
        """Atomically insert only if the RRset does not already exist.

        This is a narrow RFC 2136 prerequisite, not a general compare-and-swap.
        """
        if rrset.zone != self._config.zone:
            raise ValueError("RRset is outside configured backend zone")
        update = dns.update.Update(
            self._config.zone, keyring=self._keyring,
            keyname=self._config.key_name, keyalgorithm=self._config.key_algorithm,
        )
        update.absent(rrset.name, rrset.record_type)
        update.add(rrset.name, rrset.ttl, rrset.record_type, *rrset.values)
        try:
            response = self._transport(update, self._config.server,
                                       port=self._config.port, timeout=self._config.timeout)
        except (dns.exception.DNSException, OSError) as exc:
            raise DNSPublicationError("conditional DNS update transport failed") from exc
        if response.rcode() != dns.rcode.NOERROR:
            raise DNSPublicationError(
                f"conditional DNS update rejected: {dns.rcode.to_text(response.rcode())}"
            )

    def observe(self, rrset: RecordSet) -> RecordSet | None:
        """Return authoritative RRset or None when *authoritatively* absent.

        Uses untrusted-network-independent configured authoritative endpoint.
        An observation error never counts as an absent record.
        """
        if rrset.zone != self._config.zone:
            raise ValueError("RRset is outside configured backend zone")
        question = dns.message.make_query(rrset.name, rrset.record_type)
        question.flags &= ~dns.flags.RD
        try:
            response = dns.query.tcp(question, self._config.server,
                                     port=self._config.port, timeout=self._config.timeout)
        except (dns.exception.DNSException, OSError) as exc:
            raise DNSPublicationError("authoritative query failed") from exc
        if not response.flags & dns.flags.AA:
            raise DNSPublicationError("answer is not authoritative")
        if response.rcode() not in (dns.rcode.NOERROR, dns.rcode.NXDOMAIN):
            raise DNSPublicationError("authoritative query returned an error")
        for answer in response.answer:
            if answer.name.to_text().lower() == rrset.name and (
                dns.rdatatype.to_text(answer.rdtype) == rrset.record_type
            ):
                return RecordSet(rrset.zone, rrset.name, rrset.record_type, answer.ttl,
                                 tuple(item.to_text() for item in answer))
        return None
