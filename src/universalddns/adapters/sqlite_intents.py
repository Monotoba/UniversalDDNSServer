"""SQLite intent journal: single worker process and durable idempotency keys."""
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from ..domain import RecordSet
from ..intents import UpdateIntent, UpdateState, UpdateConflict, UnknownIntent


class SQLiteIntentJournal:
    """A connection belongs to one thread. External calls occur outside transactions."""

    def __init__(self, path: str | Path):
        self._db = sqlite3.connect(str(path), timeout=5)
        self._db.execute("PRAGMA busy_timeout=5000")
        with self._db:
            self._db.execute("""CREATE TABLE IF NOT EXISTS update_intents (
                identifier TEXT PRIMARY KEY,
                principal_id TEXT NOT NULL,
                zone TEXT NOT NULL,
                name TEXT NOT NULL,
                record_type TEXT NOT NULL,
                ttl INTEGER NOT NULL,
                values_json TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('pending','applying','applied','failed')),
                error TEXT,
                request_key TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            columns = {r[1] for r in self._db.execute("PRAGMA table_info(update_intents)")}
            if "request_key" not in columns:
                self._db.execute("ALTER TABLE update_intents ADD COLUMN request_key TEXT")
            self._db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_active_intent_per_rrset
                ON update_intents(zone,name,record_type)
                WHERE state IN ('pending','applying')""")
            self._db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS unique_request_per_principal
                ON update_intents(principal_id,request_key) WHERE request_key IS NOT NULL""")

    def enqueue(self, principal_id: str, rrset: RecordSet, request_key: str | None = None) -> UpdateIntent:
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal identifier required")
        if request_key is not None and (
            not isinstance(request_key, str) or not 1 <= len(request_key) <= 128
            or not request_key.isascii() or any(not (c.isalnum() or c in "-_.") for c in request_key)
        ):
            raise ValueError("invalid idempotency key")
        if request_key is not None:
            prior = self._db.execute(
                "SELECT identifier FROM update_intents WHERE principal_id=? AND request_key=?",
                (principal_id, request_key),
            ).fetchone()
            if prior is not None:
                existing = self.get(prior[0])
                if existing.rrset != rrset:
                    raise UpdateConflict("idempotency key reused for different update")
                return existing
        identifier = str(uuid4())
        try:
            with self._db:
                self._db.execute("""INSERT INTO update_intents
                    (identifier,principal_id,zone,name,record_type,ttl,values_json,state,request_key)
                    VALUES (?,?,?,?,?,?,?,'pending',?)""",
                    (identifier, principal_id, *rrset.key, rrset.ttl,
                     json.dumps(rrset.values), request_key))
        except sqlite3.IntegrityError as exc:
            if request_key is not None:
                prior = self._db.execute(
                    "SELECT identifier FROM update_intents WHERE principal_id=? AND request_key=?",
                    (principal_id, request_key),
                ).fetchone()
                if prior:
                    existing = self.get(prior[0])
                    if existing.rrset == rrset:
                        return existing
            raise UpdateConflict("unfinished update or duplicate request") from exc
        return self.get(identifier)

    def get(self, identifier: str) -> UpdateIntent:
        row = self._db.execute("""SELECT principal_id,zone,name,record_type,ttl,values_json,state,error
            FROM update_intents WHERE identifier=?""", (identifier,)).fetchone()
        if row is None:
            raise UnknownIntent(identifier)
        principal, zone, name, kind, ttl, values, state, error = row
        return UpdateIntent(identifier, principal,
                            RecordSet(zone, name, kind, ttl, tuple(json.loads(values))),
                            UpdateState(state), error)

    def claim(self, identifier: str) -> bool:
        with self._db:
            cur = self._db.execute("""UPDATE update_intents SET state='applying'
                WHERE identifier=? AND state='pending'""", (identifier,))
            return cur.rowcount == 1

    def finish(self, identifier: str, *, succeeded: bool, error: str | None = None) -> None:
        state = "applied" if succeeded else "failed"
        with self._db:
            cur = self._db.execute("""UPDATE update_intents SET state=?,error=?
                WHERE identifier=? AND state='applying'""",
                (state, None if succeeded else (error or "backend failure"), identifier))
            if cur.rowcount != 1:
                raise UpdateConflict("intent not in applying state")

    def mark_verified(self, identifier: str) -> None:
        """Conclude an ambiguous attempt after an authoritative observation."""
        with self._db:
            cur = self._db.execute("""UPDATE update_intents SET state='applied',error=NULL
                WHERE identifier=? AND state IN ('applying','failed')""", (identifier,))
            if cur.rowcount != 1:
                raise UpdateConflict("intent is not unresolved")

    def requeue(self, identifier: str) -> None:
        """Explicit retry, only after caller has checked authoritative state."""
        try:
            with self._db:
                cur = self._db.execute("""UPDATE update_intents SET state='pending',error=NULL
                    WHERE identifier=? AND state IN ('applying','failed')""", (identifier,))
                if cur.rowcount != 1:
                    raise UpdateConflict("intent cannot be retried")
        except sqlite3.IntegrityError as exc:
            raise UpdateConflict("another active update exists") from exc

    def pending(self) -> tuple[UpdateIntent, ...]:
        ids = self._db.execute(
            "SELECT identifier FROM update_intents WHERE state='pending' ORDER BY created_at,rowid"
        ).fetchall()
        return tuple(self.get(identifier) for (identifier,) in ids)

    def interrupted(self) -> tuple[UpdateIntent, ...]:
        ids = self._db.execute(
            "SELECT identifier FROM update_intents WHERE state='applying' ORDER BY created_at,rowid"
        ).fetchall()
        return tuple(self.get(identifier) for (identifier,) in ids)

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
