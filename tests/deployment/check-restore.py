"""Non-destructive SQLite backup + scratch restore and data equality test."""
import sqlite3
import tempfile
from pathlib import Path

live = Path("/var/lib/universalddns/state.sqlite3")
if not live.is_file():
    raise SystemExit("Installed SQLite database missing")
with tempfile.TemporaryDirectory(prefix="uddns-restore-", dir=str(live.parent)) as directory:
    backup = Path(directory) / "backup.db"
    restored = Path(directory) / "restored.db"
    with sqlite3.connect(live) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)
    with sqlite3.connect(backup) as src, sqlite3.connect(restored) as dst:
        src.backup(dst)
    with sqlite3.connect(live) as src, sqlite3.connect(restored) as dst:
        assert dst.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        tables = [x[0] for x in src.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )]
        assert tables
        assert sorted(tables) == sorted(x[0] for x in dst.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ))
        for table in tables:
            name = '"' + table.replace('"', '""') + '"'
            assert sorted(map(repr, src.execute("SELECT * FROM " + name))) == sorted(
                map(repr, dst.execute("SELECT * FROM " + name))
            ), "Restore differs: " + table
print("PASS: SQLite backup/restore and all table data match; live DB untouched")
