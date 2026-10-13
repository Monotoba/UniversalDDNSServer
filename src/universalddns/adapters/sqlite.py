"""SQLite desired-state adapter; does not perform or confirm DNS publication."""
import json
import sqlite3
from pathlib import Path
from ..domain import RecordSet, canonical_name

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS record_sets (
  zone TEXT NOT NULL,
  name TEXT NOT NULL,
  record_type TEXT NOT NULL CHECK (record_type IN ('A','AAAA')),
  ttl INTEGER NOT NULL CHECK (ttl BETWEEN 0 AND 2147483647),
  values_json TEXT NOT NULL,
  PRIMARY KEY (zone, name, record_type)
);
"""

class SQLiteRecordRepository:
    """One connection per instance; not shareable between threads."""
    def __init__(self, path: str | Path) -> None:
        self._db = sqlite3.connect(str(path))
        try:
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA busy_timeout=5000")
            self._db.executescript(_SCHEMA)
            version = self._db.execute("SELECT version FROM schema_meta").fetchone()
            if version is None:
                with self._db:
                    self._db.execute("INSERT INTO schema_meta VALUES (1)")
            elif version[0] != 1:
                raise RuntimeError("unsupported database schema version")
        except BaseException:
            self._db.close()
            raise

    def get(self, zone: str, name: str, record_type: str) -> RecordSet | None:
        row = self._db.execute(
            "SELECT ttl, values_json FROM record_sets WHERE zone=? AND name=? AND record_type=?",
            (canonical_name(zone), canonical_name(name), record_type.upper()),
        ).fetchone()
        if row is None:
            return None
        return RecordSet(zone, name, record_type, row[0], tuple(json.loads(row[1])))

    def put(self, rrset: RecordSet) -> bool:
        with self._db:
            if self.get(*rrset.key) == rrset:
                return False
            self._db.execute(
                "INSERT INTO record_sets(zone,name,record_type,ttl,values_json) VALUES (?,?,?,?,?) "
                "ON CONFLICT(zone,name,record_type) DO UPDATE SET ttl=excluded.ttl,values_json=excluded.values_json",
                (*rrset.key, rrset.ttl, json.dumps(rrset.values)),
            )
            return True

    def delete(self, zone: str, name: str, record_type: str) -> bool:
        with self._db:
            cursor = self._db.execute(
                "DELETE FROM record_sets WHERE zone=? AND name=? AND record_type=?",
                (canonical_name(zone), canonical_name(name), record_type.upper()),
            )
            return cursor.rowcount > 0

    def close(self) -> None:
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
