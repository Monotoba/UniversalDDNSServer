"""Read catalog records and current token grants in one SQLite snapshot.

This is a preparation API; it does not enable live DNS publication.
"""
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .domain import RecordSet
from .http_api import APIPrincipal
from .record_scopes import validate_catalog_grants


def catalog_snapshot(path: str | Path,
                     configured: dict[str, RecordSet],
                     *, max_records: int = 1000
                     ) -> tuple[dict[str, RecordSet], tuple[APIPrincipal, ...]]:
    """Atomically observe staged templates and unrevoked token scopes."""
    if type(max_records) is not int or not 1 <= max_records <= 1000:
        raise ValueError("invalid snapshot record limit")
    with closing(sqlite3.connect(str(path), timeout=5)) as conn:
        conn.execute("BEGIN")
        try:
            rows = conn.execute(
                "SELECT record_id,zone,name,record_type,ttl,values_json "
                "FROM managed_records WHERE active=1 ORDER BY record_id LIMIT ?",
                (max_records + 1,),
            ).fetchall()
            if len(rows) > max_records:
                raise ValueError("too many active records")
            combined = dict(configured)
            keys = {record.key for record in configured.values()}
            for identifier, zone, name, record_type, ttl, values in rows:
                record = RecordSet(zone, name, record_type, ttl, tuple(json.loads(values)))
                if identifier in combined or record.key in keys:
                    raise ValueError("conflicting staged record")
                combined[identifier] = record
                keys.add(record.key)
            token_rows = conn.execute(
                "SELECT principal,digest,scopes,records "
                "FROM api_tokens WHERE revoked=0"
            ).fetchall()
            principals = tuple(
                APIPrincipal(principal, digest, frozenset(json.loads(scopes)),
                             frozenset(json.loads(ids)))
                for principal, digest, scopes, ids in token_rows
            )
            validate_catalog_grants(configured, combined, principals)
            return combined, principals
        finally:
            conn.rollback()
