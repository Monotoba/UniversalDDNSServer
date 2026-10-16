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
        self.db.execute("""CREATE TABLE IF NOT EXISTS credential_audit (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL CHECK(action IN ('issued','revoked')),
            credential_reference TEXT NOT NULL,
            principal TEXT NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        self.db.commit()

    def issue(self, principal: str, scopes: frozenset[str], records: frozenset[str]) -> str:
        if not principal.strip() or not scopes or not records:
            raise ValueError("principal, scopes and records required")
        token = secrets.token_urlsafe(48)
        with self.db:
            cursor = self.db.execute("INSERT INTO api_tokens VALUES(?,?,?,?,0)",
                                     (hashlib.sha256(token.encode()).hexdigest(), principal,
                                      json.dumps(sorted(scopes)), json.dumps(sorted(records))))
            self.db.execute(
                "INSERT INTO credential_audit(action,credential_reference,principal) "
                "VALUES ('issued',?,?)", (f"cred-{cursor.lastrowid}", principal))
        return token

    def revoke(self, token: str) -> bool:
        with self.db:
            row = self.db.execute(
                "SELECT rowid,principal FROM api_tokens WHERE digest=? AND revoked=0",
                (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            if row is None:
                return False
            self.db.execute("UPDATE api_tokens SET revoked=1 WHERE rowid=?", (row[0],))
            self.db.execute(
                "INSERT INTO credential_audit(action,credential_reference,principal) "
                "VALUES ('revoked',?,?)", (f"cred-{row[0]}", row[1]))
            return True

    def principals(self) -> tuple[APIPrincipal, ...]:
        rows = self.db.execute("SELECT principal,digest,scopes,records FROM api_tokens WHERE revoked=0").fetchall()
        return tuple(APIPrincipal(p, d, frozenset(json.loads(s)), frozenset(json.loads(r)))
                     for p, d, s, r in rows)

    def list_metadata(self) -> tuple[dict[str, object], ...]:
        """Local credential inventory; never expose digests or bearer tokens."""
        rows = self.db.execute(
            "SELECT rowid,principal,scopes,records,revoked FROM api_tokens ORDER BY principal, rowid"
        ).fetchall()
        return tuple({
            "reference": f"cred-{rowid}",
            "principal": principal,
            "scopes": sorted(json.loads(scopes)),
            "records": sorted(json.loads(records)),
            "revoked": bool(revoked),
        } for rowid, principal, scopes, records, revoked in rows)

    def blocking_grants(self, record_id: str) -> tuple[dict[str, object], ...]:
        """List active credential metadata that blocks catalog reactivation.

        Never return bearer tokens or credential hashes. Multiple grants from
        the same principal remain distinct, since each requires revocation.
        """
        if not record_id or not isinstance(record_id, str):
            raise ValueError("record identifier required")
        rows = self.db.execute(
            "SELECT rowid,principal,scopes,records FROM api_tokens "
            "WHERE revoked=0 ORDER BY principal,rowid"
        ).fetchall()
        return tuple({
            "reference": f"cred-{rowid}",
            "principal": principal,
            "scopes": sorted(json.loads(scopes)),
            "records": sorted(json.loads(records)),
        } for rowid, principal, scopes, records in rows
            if record_id in json.loads(records))

    def revoke_reference(self, reference: str) -> bool:
        """Revoke by exact local credential reference, without the bearer."""
        if not isinstance(reference, str) or not reference.startswith("cred-"):
            raise ValueError("invalid credential reference")
        identifier = reference[5:]
        if not identifier.isascii() or not identifier.isdecimal() or not 1 <= len(identifier) <= 18 or int(identifier) < 1:
            raise ValueError("invalid credential reference")
        with self.db:
            row = self.db.execute(
                "SELECT principal FROM api_tokens WHERE rowid=? AND revoked=0",
                (int(identifier),)).fetchone()
            if row is None:
                return False
            self.db.execute(
                "UPDATE api_tokens SET revoked=1 WHERE rowid=?", (int(identifier),))
            self.db.execute(
                "INSERT INTO credential_audit(action,credential_reference,principal) "
                "VALUES ('revoked',?,?)", (reference, row[0]))
            return True

    def audit_history(self, *, limit: int = 100) -> tuple[dict[str, object], ...]:
        """Newest nonsecret local credential events, bounded to 1000."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("invalid history limit")
        rows = self.db.execute(
            "SELECT event_id,action,credential_reference,principal,recorded_at "
            "FROM credential_audit ORDER BY event_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return tuple({
            "event_id": event_id, "action": action,
            "reference": reference, "principal": principal,
            "recorded_at": recorded_at,
        } for event_id, action, reference, principal, recorded_at in rows)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
