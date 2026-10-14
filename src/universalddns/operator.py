"""Local operator CLI for durable update intents (never exposed via HTTP)."""
import argparse
import json

from .intents import UpdateState
from .runtime import factories, load_settings


def describe(intent):
    return {
        "id": intent.identifier,
        "principal": intent.principal_id,
        "state": intent.state.value,
        "zone": intent.rrset.zone,
        "name": intent.rrset.name,
        "type": intent.rrset.record_type,
        "ttl": intent.rrset.ttl,
        "values": list(intent.rrset.values),
        "error": intent.error,
    }


def main():
    parser = argparse.ArgumentParser(description="Local UniversalDDNS intent operations")
    parser.add_argument("--config", required=True)
    sub = parser.add_subparsers(dest="operation", required=True)
    listing = sub.add_parser("list", help="List bounded journal intents")
    listing.add_argument("--state", action="append",
                         choices=[state.value for state in UpdateState],
                         default=None)
    listing.add_argument("--limit", type=int, default=50)
    showing = sub.add_parser("show", help="Inspect one intent")
    showing.add_argument("identifier")
    reconciling = sub.add_parser(
        "reconcile", help="Observe authoritative DNS and resolve only if already applied"
    )
    reconciling.add_argument("identifier")
    args = parser.parse_args()
    settings = load_settings(args.config)
    journal_factory, orchestrator_factory, _ = factories(settings)
    with journal_factory() as journal:
        if args.operation == "list":
            states = tuple(args.state or ["pending", "applying", "failed"])
            result = [describe(intent) for intent in
                      journal.list_by_state(states, limit=args.limit)]
        elif args.operation == "show":
            result = describe(journal.get(args.identifier))
        else:
            # No implicit retry: a mismatched or unavailable observation leaves
            # the intent unresolved. Operators must not reissue uncertain writes.
            intent = orchestrator_factory(journal).reconcile(args.identifier, retry=False)
            result = describe(intent)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
