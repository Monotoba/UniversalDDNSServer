"""Pre-alpha authenticated HTTP intake; DNS network writes belong to workers."""
import hashlib
import ipaddress
import hmac
import re
import time
from dataclasses import dataclass
from threading import Lock
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from .audit import audit
from .adapters.sqlite_intents import SQLiteIntentJournal
from .domain import RecordSet
from .intents import UpdateConflict, UnknownIntent
from .orchestrator import UpdateOrchestrator

_KEY = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


@dataclass(frozen=True)
class APIPrincipal:
    identifier: str
    token_sha256: str
    scopes: frozenset[str]
    record_ids: frozenset[str]

    @staticmethod
    def from_token(identifier: str, token: str, scopes: frozenset[str],
                   record_ids: frozenset[str]) -> "APIPrincipal":
        if len(token) < 32:
            raise ValueError("API token must be at least 32 characters")
        return APIPrincipal(identifier, hashlib.sha256(token.encode()).hexdigest(),
                            scopes, record_ids)


class RecordAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address: str = Field(min_length=3, max_length=45)
    request_id: str = Field(min_length=1, max_length=128)


class RateGate:
    """Process-local fixed-window limit; not a distributed production limiter."""

    def __init__(self, limit: int = 60, seconds: int = 60):
        if limit < 1 or seconds < 1:
            raise ValueError("invalid rate limit")
        self.limit, self.seconds = limit, seconds
        self._lock = Lock()
        self._hits: dict[str, tuple[int, int]] = {}

    def allow(self, identifier: str) -> bool:
        now = int(time.monotonic() // self.seconds)
        with self._lock:
            window, count = self._hits.get(identifier, (-1, 0))
            if window != now:
                count = 0
            if count >= self.limit:
                return False
            self._hits[identifier] = (now, count + 1)
            return True


def create_app(
    journal_factory: Callable[[], SQLiteIntentJournal],
    orchestrator_factory: Callable[[SQLiteIntentJournal], UpdateOrchestrator],
    records: dict[str, RecordSet],
    principals: tuple[APIPrincipal, ...] | Callable[[], tuple[APIPrincipal, ...]],
    *,
    rate_limit: int = 60,
) -> FastAPI:
    """Create an API using server-owned record mapping and token-hash configuration.

    Each request receives a fresh SQLite connection; worker execution is not exposed.
    """
    current = principals() if callable(principals) else principals
    if not current or not records:
        raise ValueError("API requires configured principals and managed records")
    gate = RateGate(rate_limit)
    app = FastAPI(title="UniversalDDNSServer", version="0.2.0a1")

    def authenticated(request: Request, authorization: str | None, scope: str) -> APIPrincipal:
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        digest = hashlib.sha256(token.encode()).hexdigest()
        identity = None
        for p in (principals() if callable(principals) else principals):
            if hmac.compare_digest(p.token_sha256, digest):
                identity = p
        if identity is None:
            audit("authentication_denied", reason="invalid_bearer")
            raise HTTPException(401, "authentication required", headers={"WWW-Authenticate": "Bearer"})
        if not gate.allow(identity.identifier):
            audit("rate_limit_denied", principal=identity.identifier)
            raise HTTPException(429, "rate limit exceeded", headers={"Retry-After": "60"})
        if scope not in identity.scopes:
            audit("scope_denied", principal=identity.identifier, scope=scope)
            raise HTTPException(403, "insufficient scope")
        request.state.principal_id = identity.identifier
        return identity

    @app.get("/health/live")
    def live():
        return {"status": "live"}

    @app.put("/api/v1/records/{record_id}/address", status_code=202)
    def update(record_id: str, body: RecordAddress, request: Request,
               authorization: str | None = Header(default=None)):
        principal = authenticated(request, authorization, "records:write")
        if record_id not in records or record_id not in principal.record_ids:
            audit("record_denied", principal=principal.identifier)
            raise HTTPException(404, "record not found")
        if not _KEY.fullmatch(body.request_id):
            raise HTTPException(422, "invalid request id")
        template = records[record_id]
        try:
            rrset = RecordSet(template.zone, template.name, template.record_type,
                              template.ttl, (body.address,))
        except ValueError as exc:
            raise HTTPException(422, "invalid address for record type") from exc
        with journal_factory() as journal:
            try:
                intent = orchestrator_factory(journal).submit(
                    principal.identifier, rrset, request_key=body.request_id)
            except UpdateConflict as exc:
                audit("submission_conflict", principal=principal.identifier, record=record_id)
                raise HTTPException(409, "conflicting update") from exc
            except ValueError as exc:
                raise HTTPException(422, "invalid update") from exc
            except Exception as exc:
                from .intents import PermissionDenied
                if isinstance(exc, PermissionDenied):
                    audit("publication_denied", principal=principal.identifier, record=record_id)
                    raise HTTPException(403, "update not permitted") from exc
                raise
        audit("update_submitted", principal=principal.identifier,
              record=record_id, intent=intent.identifier)
        return {"intent_id": intent.identifier, "status": intent.state.value}


    @app.get("/nic/update", response_class=PlainTextResponse)
    def dyndns2(request: Request, authorization: str | None = Header(default=None)):
        """Experimental DynDNS2 subset: Basic token auth; queued is NOT published."""
        from .intents import PermissionDenied
        import base64
        from binascii import Error as Base64Error

        def answer(message: str) -> PlainTextResponse:
            return PlainTextResponse(message + "\\n", media_type="text/plain")

        token = ""
        if authorization and authorization.startswith("Basic "):
            try:
                decoded = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
                _, token = decoded.split(":", 1)
            except (Base64Error, UnicodeDecodeError, ValueError):
                pass
        if not token:
            audit("dyndns_authentication_denied", reason="missing_basic_token")
            return answer("badauth")
        try:
            principal = authenticated(request, "Bearer " + token, "records:write")
        except HTTPException as exc:
            return answer("911" if exc.status_code == 429 else "badauth")

        params = request.query_params
        if set(params.keys()) - {"hostname", "myip"}:
            return answer("badagent")
        hostname = params.get("hostname", "")
        address = params.get("myip", "")
        if not hostname or "," in hostname:
            return answer("notfqdn")
        matches = [(rid, rr) for rid, rr in records.items()
                   if rr.name.rstrip(".").lower() == hostname.rstrip(".").lower()
                   and rid in principal.record_ids]
        if len(matches) != 1:
            audit("dyndns_record_denied", principal=principal.identifier)
            return answer("nohost")
        record_id, template = matches[0]
        try:
            value = ipaddress.ip_address(address)
            if value.version != (4 if template.record_type == "A" else 6):
                return answer("dnserr")
            rrset = RecordSet(template.zone, template.name, template.record_type,
                              template.ttl, (str(value),))
        except ValueError:
            return answer("dnserr")
        # Response 911 explicitly signals a transient condition: do not report good
        # before the separately supervised worker has actually published DNS.
        with journal_factory() as journal:
            try:
                intent = orchestrator_factory(journal).submit(principal.identifier, rrset)
            except PermissionDenied:
                return answer("badauth")
            except (UpdateConflict, ValueError):
                return answer("dnserr")
        audit("dyndns_update_queued", principal=principal.identifier,
              record=record_id, intent=intent.identifier)
        return answer("911")

    @app.get("/api/v1/intents/{intent_id}")
    def status(intent_id: str, request: Request,
               authorization: str | None = Header(default=None)):
        principal = authenticated(request, authorization, "intents:read")
        with journal_factory() as journal:
            try:
                intent = journal.get(intent_id)
            except UnknownIntent as exc:
                raise HTTPException(404, "intent not found") from exc
        if intent.principal_id != principal.identifier or not any(
            rid in principal.record_ids and records[rid].key == intent.rrset.key
            for rid in records
        ):
            raise HTTPException(404, "intent not found")
        return {"intent_id": intent.identifier, "status": intent.state.value}

    return app
