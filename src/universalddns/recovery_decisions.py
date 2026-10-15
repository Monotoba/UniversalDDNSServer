"""Durable append-only operator assessments; never mutate DNS or update intents."""
import sqlite3
from pathlib import Path
from uuid import uuid4

from .intents import UpdateConflict, UnknownIntent

_ACTIONS = frozenset({"investigate", "propose_verify", "propose_abandon"})
_OBSERVATIONS = frozenset({"matches", "differs", "absent", "unavailable", "unknown"})


class RecoveryDecisionJournal:
    """Persist proposed decisions with a generation snapshot, not an approval."""

    def __init__(self, path: str | Path):
        self._db = sqlite3.connect(str(path), timeout=5)
        self._db.execute("PRAGMA busy_timeout=5000")
        with self._db:
            self._db.execute("""CREATE TABLE IF NOT EXISTS recovery_decisions (
                decision_id TEXT PRIMARY KEY,
                intent_id TEXT NOT NULL,
                expected_generation INTEGER NOT NULL,
                operator_id TEXT NOT NULL,
                proposed_action TEXT NOT NULL,
                observation TEXT NOT NULL,
                rationale TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            self._db.execute("""CREATE INDEX IF NOT EXISTS recovery_decisions_intent
                ON recovery_decisions(intent_id, created_at)""")
            self._db.execute("""CREATE TRIGGER IF NOT EXISTS recovery_decisions_no_update
                BEFORE UPDATE ON recovery_decisions BEGIN
                SELECT RAISE(ABORT, 'recovery decisions are append-only'); END""")
            self._db.execute("""CREATE TRIGGER IF NOT EXISTS recovery_decisions_no_delete
                BEFORE DELETE ON recovery_decisions BEGIN
                SELECT RAISE(ABORT, 'recovery decisions are append-only'); END""")

    def record(self, *, intent_id: str, expected_generation: int,
               operator_id: str, proposed_action: str,
               observation: str, rationale: str) -> str:
        if type(expected_generation) is not int or expected_generation < 0:
            raise ValueError("invalid generation")
        if not isinstance(operator_id, str) or not 1 <= len(operator_id) <= 128 or not operator_id.isascii() or not all(c.isalnum() or c in "-_." for c in operator_id):
            raise ValueError("invalid operator identity")
        if proposed_action not in _ACTIONS or observation not in _OBSERVATIONS:
            raise ValueError("invalid decision type or observation")
        if not isinstance(rationale, str) or not 1 <= len(rationale) <= 1000:
            raise ValueError("rationale required (up to 1000 characters)")
        if not isinstance(intent_id, str) or not intent_id:
            raise ValueError("intent ID required")
        # BEGIN IMMEDIATE serializes snapshot checking and insertion with any
        # concurrent SQLite writer; this is still not a DNS-side fence.
        self._db.execute("BEGIN IMMEDIATE")
        try:
            row = self._db.execute(
                "SELECT generation FROM update_intents WHERE identifier=?",
                (intent_id,)).fetchone()
            if row is None:
                raise UnknownIntent(intent_id)
            if row[0] != expected_generation:
                raise UpdateConflict("stale intent generation")
            decision_id = str(uuid4())
            self._db.execute(
                """INSERT INTO recovery_decisions
                (decision_id,intent_id,expected_generation,operator_id,
                 proposed_action,observation,rationale)
                VALUES (?,?,?,?,?,?,?)""",
                (decision_id, intent_id, expected_generation, operator_id,
                 proposed_action, observation, rationale))
            self._db.commit()
        except BaseException:
            self._db.rollback()
            raise
        return decision_id

    def list_for_intent(self, intent_id: str, *, limit: int = 100) -> tuple[dict, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("invalid limit")
        rows = self._db.execute(
            """SELECT decision_id,expected_generation,operator_id,proposed_action,
                      observation,rationale,created_at FROM recovery_decisions
               WHERE intent_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?""",
            (intent_id, limit)).fetchall()
        return tuple(dict(zip(("decision_id", "expected_generation", "operator_id",
                               "proposed_action", "observation", "rationale",
                               "created_at"), row)) for row in rows)

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
