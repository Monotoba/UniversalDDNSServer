"""Local-only credential provisioning tool. Do not expose through HTTP."""
import argparse
import json
from .runtime import load_admin_settings
from .token_store import TokenStore
from .record_catalog import RecordCatalog
from .record_snapshot import catalog_snapshot
from .local_operator import local_operator_identity


def main():
    parser = argparse.ArgumentParser(description="Manage local DDNS API tokens")
    parser.add_argument("--config", required=True)
    sub = parser.add_subparsers(dest="operation", required=True)
    issue = sub.add_parser("issue")
    issue.add_argument("--principal", required=True)
    issue.add_argument("--record", action="append", required=True)
    issue.add_argument("--scope", action="append", choices=("records:write", "intents:read"),
                       required=True)
    sub.add_parser("list", help="List local credential metadata without tokens or hashes")
    sub.add_parser("history", help="Show recent local credential issuance and revocation events")
    ref_revoke = sub.add_parser("revoke-reference", help="Locally revoke credential using inventory reference")
    ref_revoke.add_argument("--reference", required=True)
    revoke = sub.add_parser("revoke")
    revoke.add_argument("--token-stdin", action="store_true", required=True)
    args = parser.parse_args()
    settings = load_admin_settings(args.config)
    if args.operation == "issue":
        operator = local_operator_identity()
        # Initialize missing legacy catalog/token tables without activation.
        with RecordCatalog(settings.database):
            pass
        with TokenStore(settings.database):
            pass
        try:
            available, _ = catalog_snapshot(settings.database, settings.records)
        except ValueError as exc:
            parser.error(f"catalog validation failed: {exc}")
        if not set(args.record).issubset(available):
            parser.error("unknown or inactive record identifier")
        with TokenStore(settings.database) as store:
            token = store.issue(args.principal, frozenset(args.scope), frozenset(args.record), operator=operator)
        print(token)
    elif args.operation == "revoke-reference":
        operator = local_operator_identity()
        with TokenStore(settings.database) as store:
            if not store.revoke_reference(args.reference, operator=operator):
                parser.error("credential not found or already revoked")
        print("revoked")
    elif args.operation == "history":
        local_operator_identity()
        with TokenStore(settings.database) as store:
            print(json.dumps(store.audit_history(), sort_keys=True, indent=2))
    elif args.operation == "list":
        with TokenStore(settings.database) as store:
            print(json.dumps(store.list_metadata(), sort_keys=True, indent=2))
    else:
        import sys
        token = sys.stdin.readline().rstrip("\r\n")
        if not token:
            parser.error("token required on stdin")
        operator = local_operator_identity()
        with TokenStore(settings.database) as store:
            if not store.revoke(token, operator=operator):
                parser.error("token not found or already revoked")
        print("revoked")


if __name__ == "__main__":
    main()
