"""End-to-end local proposal CLI against a real SQLite journal."""
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from universalddns.adapters.sqlite_intents import SQLiteIntentJournal
from universalddns.domain import RecordSet
from universalddns.operator import main


class LocalProposalIntegrationTests(unittest.TestCase):
    def test_local_proposal_persists_and_denied_user_cannot_append(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "state.db"
            with SQLiteIntentJournal(db) as journal:
                intent = journal.enqueue("device", RecordSet(
                    "example.org", "proposal.example.org", "A", 60, ("192.0.2.81",)))
            settings = SimpleNamespace(database=db)
            cmd = ["operator", "--config", "unused", "propose", intent.identifier,
                   "--generation", "0", "--action", "investigate",
                   "--observation", "unknown", "--rationale", "Inspect worker"]

            def factories(_settings):
                return (lambda: SQLiteIntentJournal(db), None, None)

            with (patch("sys.argv", cmd),
                  patch("universalddns.operator.load_settings", return_value=settings),
                  patch("universalddns.operator.factories", side_effect=factories),
                  patch("universalddns.local_operator.os.getuid", return_value=1001),
                  patch("universalddns.local_operator.os.geteuid", return_value=1001),
                  patch("universalddns.local_operator.pwd.getpwuid",
                        return_value=SimpleNamespace(pw_name="operator1")),
                  redirect_stdout(StringIO()) as output):
                self.assertEqual(main(), 0)
                self.assertFalse(json.loads(output.getvalue())["executed"])

            with (patch("sys.argv", ["operator", "--config", "unused", "proposals",
                                      intent.identifier]),
                  patch("universalddns.operator.load_settings", return_value=settings),
                  patch("universalddns.operator.factories", side_effect=factories),
                  redirect_stdout(StringIO()) as output):
                self.assertEqual(main(), 0)
                proposals = json.loads(output.getvalue())
            self.assertEqual(len(proposals), 1)
            self.assertEqual(proposals[0]["operator_id"], "operator1")

            with (patch("sys.argv", cmd),
                  patch("universalddns.operator.load_settings", return_value=settings),
                  patch("universalddns.operator.factories", side_effect=factories),
                  patch("universalddns.local_operator.os.getuid", return_value=0),
                  patch("universalddns.local_operator.os.geteuid", return_value=0),
                  redirect_stderr(StringIO())):
                self.assertEqual(main(), 4)
            with SQLiteIntentJournal(db) as journal:
                self.assertEqual(journal.generation(intent.identifier), 0)
            from universalddns.recovery_decisions import RecoveryDecisionJournal
            with RecoveryDecisionJournal(db) as decisions:
                self.assertEqual(len(decisions.list_for_intent(intent.identifier)), 1)
