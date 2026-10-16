#!/usr/bin/env python3
"""Non-destructive disposable VM catalog/credential lifecycle check.

Uses a fresh temporary SQLite DB, no installed service DB, HTTP, or DNS writes.
"""
import json
import tempfile
from pathlib import Path

from universalddns.domain import RecordSet
from universalddns.record_catalog import RecordCatalog
from universalddns.record_snapshot import catalog_snapshot
from universalddns.token_store import TokenStore


def check() -> None:
    with tempfile.TemporaryDirectory(prefix="uddns-catalog-check-") as directory:
        database = Path(directory) / "scratch.sqlite3"
        record = RecordSet("lab.invalid", "candidate.lab.invalid", "A",
                           60, ("192.0.2.40",))
        with RecordCatalog(database) as catalog:
            assert catalog.create("candidate", record) == 1
            assert catalog.active_count() == 0
            assert catalog.set_active("candidate", expected_revision=1, active=True) == 2
        # Initialize token table before requesting a combined catalog snapshot.
        with TokenStore(database) as tokens:
            token = tokens.issue("fixture-client",
                                 frozenset({"records:write", "intents:read"}),
                                 frozenset({"candidate"}), operator="fixture")
            reference = tokens.blocking_grants("candidate")[0]["reference"]
            assert reference.startswith("cred-")
        available, principals = catalog_snapshot(database, {})
        assert "candidate" in available
        assert len(principals) == 1
        assert principals[0].record_ids == frozenset({"candidate"})
        with RecordCatalog(database) as catalog:
            assert catalog.set_active("candidate", expected_revision=2, active=False) == 3
            try:
                catalog.set_active("candidate", expected_revision=3, active=True)
            except ValueError as exc:
                assert "revoke" in str(exc)
            else:
                raise AssertionError("reactivation unexpectedly accepted stale grant")
        with TokenStore(database) as tokens:
            assert tokens.revoke_reference(reference, operator="fixture")
            assert not tokens.revoke_reference(reference, operator="fixture")
            assert not tokens.principals()
            history = tokens.audit_history()
            assert [event["action"] for event in history] == ["revoked", "issued"]
            assert all(event["operator"] == "fixture" for event in history)
            assert token not in json.dumps(history)
            assert token not in json.dumps(tokens.list_metadata())
        with RecordCatalog(database) as catalog:
            assert catalog.set_active("candidate", expected_revision=3, active=True) == 4
        with TokenStore(database) as tokens:
            replacement = tokens.issue("replacement",
                                       frozenset({"records:write"}),
                                       frozenset({"candidate"}))
            assert replacement != token
        available, principals = catalog_snapshot(database, {})
        assert "candidate" in available
        assert {identity.identifier for identity in principals} == {"replacement"}
    print("PASS: isolated SQLite catalog/credential lifecycle and audit")


if __name__ == "__main__":
    check()
