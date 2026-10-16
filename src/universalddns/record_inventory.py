"""Standalone read-only staged record inventory; not wired to broker or CLI."""
import os
import sqlite3
from pathlib import Path
from urllib.parse import quote

MAX_RECORDS = 1_000_000_000


def read_record_inventory(path: str | Path) -> dict[str, int]:
    """Count staged records without creating files, tables, journals or migrations.

    Caller authentication and broker response handling are deliberately outside
    this module. Never pass a client-provided database path.
    """
    db_path = os.path.abspath(os.fspath(path))
    uri = "file:" + quote(db_path, safe="/") + "?mode=ro&immutable=0"
    try:
        with sqlite3.connect(uri, uri=True, timeout=0.2) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA busy_timeout=200")
            columns = db.execute("PRAGMA table_info(managed_records)").fetchall()
            names = {row[1] for row in columns}
            expected = {
                "record_id", "zone", "name", "record_type", "ttl",
                "values_json", "revision", "active",
            }
            if not expected.issubset(names):
                raise ValueError("inventory unavailable")
            row = db.execute(
                "SELECT COUNT(*), "
                "COALESCE(SUM(CASE WHEN active=1 THEN 1 ELSE 0 END),0), "
                "COALESCE(SUM(CASE WHEN active=0 THEN 1 ELSE 0 END),0) "
                "FROM managed_records"
            ).fetchone()
            if row is None:
                raise ValueError("inventory unavailable")
            total, active, inactive = row
            if any(type(n) is not int or not 0 <= n <= MAX_RECORDS
                   for n in (total, active, inactive)) or total != active + inactive:
                raise ValueError("inventory unavailable")
            return {
                "total_records": total,
                "staged_active_records": active,
                "staged_inactive_records": inactive,
            }
    except (sqlite3.Error, OSError) as exc:
        raise ValueError("inventory unavailable") from exc
