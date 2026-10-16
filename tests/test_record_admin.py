"""Exercise local record administration with actual SQLite persistence."""
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from universalddns.domain import RecordSet
from universalddns.record_admin import main
from universalddns.record_catalog import RecordCatalog


class RecordAdminTests(unittest.TestCase):
    def test_create_update_list_and_static_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "state.db"
            static = RecordSet("example.org", "static.example.org",
                               "A", 60, ("192.0.2.1",))
            settings = SimpleNamespace(database=db,
                                       dns=SimpleNamespace(zone="example.org"),
                                       records={"static": static})
            base = ["record-admin", "--config", "unused"]
            create = base + ["create", "dynamic", "--name", "dynamic.example.org",
                             "--type", "A", "--ttl", "120",
                             "--address", "192.0.2.12"]
            def call(arguments, *, authorized=True):
                with (patch("sys.argv", arguments),
                      patch("universalddns.record_admin.load_admin_settings",
                            return_value=settings),
                      patch("universalddns.record_admin.local_operator_identity",
                            side_effect=None if authorized else PermissionError("not authorized"),
                            return_value="operator1"),
                      redirect_stdout(StringIO()) as output,
                      redirect_stderr(StringIO())):
                    status = main()
                    return status, output.getvalue()
            self.assertEqual(call(create, authorized=False)[0], 4)
            self.assertEqual(call(create)[0], 0)
            self.assertEqual(call(create)[0], 4)
            listed, body = call(base + ["list"])
            self.assertEqual(listed, 0)
            self.assertEqual(json.loads(body)["records"][0]["id"], "dynamic")
            self.assertEqual(json.loads(body)["records"][0]["revision"], 1)
            modify = base + ["update", "dynamic", "--name", "dynamic.example.org",
                             "--type", "A", "--ttl", "180",
                             "--address", "192.0.2.13", "--revision", "1"]
            self.assertEqual(call(modify)[0], 0)
            self.assertEqual(call(modify)[0], 4)
            self.assertEqual(call(base + ["create", "static",
                                         "--name", "other.example.org", "--type", "A",
                                         "--ttl", "60", "--address", "192.0.2.2"])[0], 4)
            self.assertEqual(call(base + ["create", "other",
                                         "--name", "static.example.org", "--type", "A",
                                         "--ttl", "60", "--address", "192.0.2.2"])[0], 4)
            with RecordCatalog(db) as catalog:
                self.assertEqual(catalog.get("dynamic")[1], 2)
                self.assertEqual(catalog.get("dynamic")[0].values, ("192.0.2.13",))
