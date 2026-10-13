"""Local-only credential provisioning tool. Do not expose through HTTP."""
import argparse
from .runtime import load_settings
from .token_store import TokenStore


def main():
    parser = argparse.ArgumentParser(description="Manage local DDNS API tokens")
    parser.add_argument("--config", required=True)
    sub = parser.add_subparsers(dest="operation", required=True)
    issue = sub.add_parser("issue")
    issue.add_argument("--principal", required=True)
    issue.add_argument("--record", action="append", required=True)
    issue.add_argument("--scope", action="append", choices=("records:write", "intents:read"),
                       required=True)
    revoke = sub.add_parser("revoke")
    revoke.add_argument("--token-stdin", action="store_true", required=True)
    args = parser.parse_args()
    settings = load_settings(args.config)
    if args.operation == "issue":
        if not set(args.record).issubset(settings.records):
            parser.error("unknown record identifier")
        with TokenStore(settings.database) as store:
            token = store.issue(args.principal, frozenset(args.scope), frozenset(args.record))
        print(token)
    else:
        import sys
        token = sys.stdin.readline().rstrip("\r\n")
        if not token:
            parser.error("token required on stdin")
        with TokenStore(settings.database) as store:
            if not store.revoke(token):
                parser.error("token not found or already revoked")
        print("revoked")


if __name__ == "__main__":
    main()
