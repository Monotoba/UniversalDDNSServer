"""SQLite store for revocable API bearer tokens."""
import hashlib
import json
import secrets
import sqlite3
from pathlib import Path
from .http_api import APIPrincipal

class TokenStore:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(str(path))
        self.db.execute("""CREATE TABLE IF NOT EXISTS api_tokens (
            digest TEXT PRIMARY KEY, principal TEXT NOT NULL,
            scopes TEXT NOT NULL, records TEXT NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0
        )""")
        self.db.commit()

    def issue(self, principal: str, scopes: frozenset[str], records: frozenset[str]) -> str:
        if not principal.strip() or not scopes or not records:
            raise ValueError("principal, scopes and records required")
        token = secrets.token_urlsafe(48)
        with self.db:
            self.db.execute("INSERT INTO api_tokens VALUES(?,?,?,?,0)",
                            (hashlib.sha256(token.encode()).hexdigest(), principal,
                             json.dumps(sorted(scopes)), json.dumps(sorted(records))))
        return token

    def revoke(self, token: str) -> bool:
        with self.db:
            return self.db.execute("UPDATE api_tokens SET revoked=1 WHERE digest=? AND revoked=0",
                                   (hashlib.sha256(token.encode()).hexdigest(),)).rowcount == 1

    def principals(self) -> tuple[APIPrincipal, ...]:
        rows = self.db.execute("SELECT principal,digest,scopes,records FROM api_tokens WHERE revoked=0").fetchall()
        return tuple(APIPrincipal(p, d, frozenset(json.loads(s)), frozenset(json.loads(r)))
                     for p, d, s, r in rows)

    def list_metadata(self) -> tuple[dict[str, object], ...]:
        """Local credential inventory; never expose digests or bearer tokens."""
        rows = self.db.execute(
            "SELECT principal,scopes,records,revoked FROM api_tokens ORDER BY principal, rowid"
        ).fetchall()
        return tuple({
            "principal": principal,
            "scopes": sorted(json.loads(scopes)),
            "records": sorted(json.loads(records)),
            "revoked": bool(revoked),
        } for principal, scopes, records, revoked in rows)

    def blocking_grants(self, record_id: str) -> tuple[dict[str, object], ...]:
        """List active credential metadata that blocks catalog reactivation.

        Never return bearer tokens or credential hashes. Multiple grants from
        the same principal remain distinct, since each requires revocation.
        """
        if not record_id or not isinstance(record_id, str):
            raise ValueError("record identifier required")
        rows = self.db.execute(
            "SELECT principal,scopes,records FROM api_tokens "
            "WHERE revoked=0 ORDER BY principal,rowid"
        ).fetchall()
        return tuple({
            "principal": principal,
            "scopes": sorted(json.loads(scopes)),
            "records": sorted(json.loads(records)),
        } for principal, scopes, records in rows
            if record_id in json.loads(records))

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
