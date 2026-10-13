import sqlite3
import tempfile
from pathlib import Path
import unittest
from universalddns.domain import RecordSet
from universalddns.adapters.sqlite import SQLiteRecordRepository
from universalddns.ports import RecordRepository

class SQLiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "state.db"
        self.rr = RecordSet("example.org","a.example.org","A",120,("192.0.2.4",))
    def tearDown(self):
        self.temp.cleanup()
    def test_contract_noop_update_delete(self):
        with SQLiteRecordRepository(self.path) as repo:
            self.assertIsInstance(repo, RecordRepository)
            self.assertIsNone(repo.get(*self.rr.key))
            self.assertTrue(repo.put(self.rr))
            self.assertFalse(repo.put(self.rr))
            self.assertEqual(repo.get(*self.rr.key), self.rr)
            changed = RecordSet("example.org","a.example.org","A",90,("192.0.2.5",))
            self.assertTrue(repo.put(changed))
            self.assertEqual(repo.get(*changed.key), changed)
            self.assertTrue(repo.delete(*changed.key))
            self.assertFalse(repo.delete(*changed.key))
    def test_durability(self):
        with SQLiteRecordRepository(self.path) as repo:
            repo.put(self.rr)
        with SQLiteRecordRepository(self.path) as repo:
            self.assertEqual(repo.get(*self.rr.key), self.rr)
    def test_invalid_name_does_not_execute_sql(self):
        with SQLiteRecordRepository(self.path) as repo:
            with self.assertRaises(ValueError):
                repo.get("example.org';DROP TABLE record_sets;--","a.example.org","A")
            self.assertTrue(repo.put(self.rr))
    def test_unknown_schema_version(self):
        with SQLiteRecordRepository(self.path):
            pass
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE schema_meta SET version=99")
        with self.assertRaises(RuntimeError):
            SQLiteRecordRepository(self.path)
