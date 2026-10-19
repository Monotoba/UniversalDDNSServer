"""Integration tests for the updater's SQLite restoration code."""

import os
import pwd
import grp
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

UPDATER = Path(__file__).parent / "deployment/update-vm.sh"


class SQLiteRestoreTests(unittest.TestCase):

    def test_restores_original_database(self):
        source = UPDATER.read_text()
        code = source.split(
            "<<'PYDBRESTORE'\n", 1
        )[1].split("\nPYDBRESTORE", 1)[0]

        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "live.db"
            backup = Path(tmp) / "backup.db"

            with sqlite3.connect(live) as db:
                db.execute("CREATE TABLE t(v TEXT)")
                db.execute("INSERT INTO t VALUES ('original')")
                db.commit()
                with sqlite3.connect(backup) as dst:
                    db.backup(dst)

            with sqlite3.connect(live) as db:
                db.execute("INSERT INTO t VALUES ('upgraded')")
                db.commit()

            live.chmod(0o600)
            user = pwd.getpwuid(os.getuid())
            group = grp.getgrgid(os.getgid())

            with patch.object(sys, "argv",
                              ["restore", str(backup), str(live)]):
                with patch.object(pwd, "getpwnam", return_value=user):
                    with patch.object(grp, "getgrnam",
                                      return_value=group):
                        exec(compile(code, "<restore>", "exec"))

            with sqlite3.connect(live) as db:
                self.assertEqual(
                    db.execute("SELECT v FROM t").fetchall(),
                    [("original",)]
                )


    def test_rejects_incorrect_database_permissions(self):
        source = UPDATER.read_text()
        code = source.split(
            "<<'PYDBRESTORE'\n", 1
        )[1].split("\nPYDBRESTORE", 1)[0]

        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "live.db"
            backup = Path(tmp) / "backup.db"

            for path in (live, backup):
                with sqlite3.connect(path) as db:
                    db.execute("CREATE TABLE t(v TEXT)")

            live.chmod(0o644)
            user = pwd.getpwuid(os.getuid())
            group = grp.getgrgid(os.getgid())

            with patch.object(
                sys, "argv",
                ["restore", str(backup), str(live)]
            ):
                with patch.object(
                    pwd, "getpwnam", return_value=user
                ):
                    with patch.object(
                        grp, "getgrnam", return_value=group
                    ):
                        with self.assertRaisesRegex(
                            RuntimeError, "permissions mismatch"
                        ):
                            exec(compile(code, "<restore>", "exec"))


    def test_wrong_owner_does_not_modify_database(self):
        code = UPDATER.read_text().split(
            "<<'PYDBRESTORE'\n", 1
        )[1].split("\nPYDBRESTORE", 1)[0]

        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "live.db"
            backup = Path(tmp) / "backup.db"

            with sqlite3.connect(live) as db:
                db.execute("CREATE TABLE t(v TEXT)")
                db.execute("INSERT INTO t VALUES ('live')")
                db.commit()

            with sqlite3.connect(backup) as db:
                db.execute("CREATE TABLE t(v TEXT)")
                db.execute("INSERT INTO t VALUES ('backup')")
                db.commit()

            live.chmod(0o600)
            user = pwd.getpwuid(os.getuid())
            wrong_user = type("User", (), {
                "pw_uid": user.pw_uid + 100000
            })()

            with patch.object(
                sys, "argv", ["restore", str(backup), str(live)]
            ), patch.object(
                pwd, "getpwnam", return_value=wrong_user
            ), patch.object(
                grp, "getgrnam",
                return_value=grp.getgrgid(os.getgid())
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "ownership mismatch"
                ):
                    exec(compile(code, "<restore>", "exec"))

            with sqlite3.connect(live) as db:
                self.assertEqual(
                    db.execute("SELECT v FROM t").fetchall(),
                    [("live",)]
                )


    def test_missing_database_is_not_created(self):
        code = UPDATER.read_text().split(
            "<<'PYDBRESTORE'\n", 1
        )[1].split("\nPYDBRESTORE", 1)[0]

        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "missing.db"
            backup = Path(tmp) / "backup.db"

            with sqlite3.connect(backup) as db:
                db.execute("CREATE TABLE t(v TEXT)")

            with patch.object(
                sys, "argv", ["restore", str(backup), str(live)]
            ):
                with self.assertRaises(FileNotFoundError):
                    exec(compile(code, "<restore>", "exec"))

            self.assertFalse(live.exists())


if __name__ == "__main__":
    unittest.main()
