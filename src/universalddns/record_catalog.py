
"""SQLite catalog for durable, explicitly managed A/AAAA record templates.

Not yet wired to HTTP intake or worker authorization: configured records remain
the sole active source until a separate migration/activation change is reviewed.
"""

import json
import sqlite3
from pathlib import Path

from .domain import RecordSet


class RecordCatalog:
    def __init__(self, path: str | Path):
        self._db = sqlite3.connect(str(path), timeout=5)
        self._db.execute("PRAGMA busy_timeout=5000")

        with self._db:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS managed_records (
                    record_id TEXT PRIMARY KEY,
                    zone TEXT NOT NULL,
                    name TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    ttl INTEGER NOT NULL,
                    values_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1
                        CHECK (revision >= 1),
                    active INTEGER NOT NULL DEFAULT 0
                        CHECK (active IN (0,1)),
                    UNIQUE (zone,name,record_type)
                )"""
            )

            columns = {
                row[1]
                for row in self._db.execute(
                    "PRAGMA table_info(managed_records)"
                )
            }

            if "active" not in columns:
                self._db.execute(
                    "ALTER TABLE managed_records "
                    "ADD COLUMN active INTEGER NOT NULL DEFAULT 0 "
                    "CHECK (active IN (0,1))"
                )

    def set_active(
        self,
        record_id: str,
        *,
        expected_revision: int,
        active: bool,
    ) -> int:
        """Atomically stage activation metadata, without granting DNS authority."""
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("invalid expected revision")

        if type(active) is not bool:
            raise ValueError("active must be boolean")

        # BEGIN IMMEDIATE obtains the SQLite write reservation before
        # checking outstanding token grants. This prevents another
        # writer from changing those grants between the check and
        # the activation update.
        self._db.execute("BEGIN IMMEDIATE")

        try:
            existing = self._db.execute(
                "SELECT active FROM managed_records "
                "WHERE record_id=? AND revision=?",
                (record_id, expected_revision),
            ).fetchone()

            if existing is None:
                raise ValueError("missing record or stale revision")

            # Reactivating a previously inactive record must not
            # silently revive access through existing bearer tokens.
            if active and not existing[0]:
                token_table = self._db.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type='table' AND name='api_tokens'"
                ).fetchone()

                if token_table:
                    for (grants_json,) in self._db.execute(
                        "SELECT records FROM api_tokens WHERE revoked=0"
                    ):
                        if record_id in json.loads(grants_json):
                            raise ValueError(
                                "reactivation refused: revoke existing "
                                "token grants first"
                            )

            cur = self._db.execute(
                "UPDATE managed_records "
                "SET active=?, revision=revision+1 "
                "WHERE record_id=? AND revision=?",
                (int(active), record_id, expected_revision),
            )

            if cur.rowcount != 1:
                raise ValueError("missing record or stale revision")

            self._db.commit()

        except BaseException:
            self._db.rollback()
            raise

        return expected_revision + 1

    def active_count(self) -> int:
        """Count staged active records before building a bounded mapping."""
        return self._db.execute(
            "SELECT COUNT(*) FROM managed_records WHERE active=1"
        ).fetchone()[0]

    def active_records(
        self,
        *,
        limit: int = 100,
    ) -> tuple[tuple[str, RecordSet, int], ...]:
        """Return staged active entries. Live runtime is not yet catalog-backed."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("invalid record list limit")

        rows = self._db.execute(
            "SELECT record_id FROM managed_records WHERE active=1 "
            "ORDER BY record_id LIMIT ?",
            (limit,),
        ).fetchall()

        return tuple(
            (rid, *self.get(rid))
            for (rid,) in rows
        )

    def create(self, record_id: str, record: RecordSet) -> int:
        if (
            not isinstance(record_id, str)
            or not 1 <= len(record_id) <= 128
            or not record_id.isascii()
            or any(
                not (c.isalnum() or c in "-_.")
                for c in record_id
            )
        ):
            raise ValueError("invalid record identifier")

        if not isinstance(record, RecordSet):
            raise TypeError("record must be a RecordSet")

        try:
            with self._db:
                self._db.execute(
                    """INSERT INTO managed_records
                    (record_id,zone,name,record_type,ttl,values_json)
                    VALUES (?,?,?,?,?,?)""",
                    (
                        record_id,
                        *record.key,
                        record.ttl,
                        json.dumps(record.values),
                    ),
                )

        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "duplicate record identifier or DNS RRset"
            ) from exc

        return 1

    def get(self, record_id: str) -> tuple[RecordSet, int] | None:
        row = self._db.execute(
            """SELECT zone,name,record_type,ttl,values_json,revision
               FROM managed_records WHERE record_id=?""",
            (record_id,),
        ).fetchone()

        if row is None:
            return None

        zone, name, record_type, ttl, values, revision = row

        return (
            RecordSet(
                zone,
                name,
                record_type,
                ttl,
                tuple(json.loads(values)),
            ),
            revision,
        )

    def list_records(
        self,
        *,
        limit: int = 100,
    ) -> tuple[tuple[str, RecordSet, int], ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("invalid record list limit")

        ids = self._db.execute(
            "SELECT record_id FROM managed_records "
            "ORDER BY record_id LIMIT ?",
            (limit,),
        ).fetchall()

        return tuple(
            (rid, *self.get(rid))
            for (rid,) in ids
        )

    def update(
        self,
        record_id: str,
        record: RecordSet,
        *,
        expected_revision: int,
    ) -> int:
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("invalid expected revision")

        if not isinstance(record, RecordSet):
            raise TypeError("record must be a RecordSet")

        try:
            with self._db:
                cur = self._db.execute(
                    """UPDATE managed_records
                       SET zone=?,name=?,record_type=?,
                           ttl=?,values_json=?,revision=revision+1
                       WHERE record_id=? AND revision=?""",
                    (
                        *record.key,
                        record.ttl,
                        json.dumps(record.values),
                        record_id,
                        expected_revision,
                    ),
                )

                if cur.rowcount != 1:
                    raise ValueError(
                        "missing record or stale revision"
                    )

        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "DNS RRset already managed by another record"
            ) from exc

        return expected_revision + 1

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
