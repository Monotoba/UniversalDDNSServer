"""Local operator CLI for durable update intents (never exposed via HTTP)."""
import argparse
import json
import sys

from dns.exception import DNSException

from .intents import PermissionDenied, UnknownIntent, UpdateConflict, UpdateState
from .runtime import factories, load_settings
from .local_operator import local_operator_identity
from .recovery_decisions import RecoveryDecisionJournal


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
    assessing = sub.add_parser("assess", help="Read-only, audited recovery assessment")
    assessing.add_argument("identifier")
    proposals = sub.add_parser("propose", help="Record a local non-executable recovery proposal")
    proposals.add_argument("identifier")
    proposals.add_argument("--generation", type=int, required=True)
    proposals.add_argument("--action", choices=("investigate", "propose_verify",
                                                 "propose_abandon"), required=True)
    proposals.add_argument("--observation", choices=("matches", "differs", "absent",
                                                      "unavailable", "unknown"), required=True)
    proposals.add_argument("--rationale", required=True)
    history = sub.add_parser("proposals", help="List recorded recovery proposals")
    history.add_argument("identifier")
    history.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    settings = load_settings(args.config)
    journal_factory, orchestrator_factory, _ = factories(settings)
    try:
        with journal_factory() as journal:
            if args.operation == "list":
                states = tuple(args.state or ["pending", "applying", "failed"])
                result = [describe(intent) for intent in
                          journal.list_by_state(states, limit=args.limit)]
            elif args.operation == "show":
                result = describe(journal.get(args.identifier))
            elif args.operation == "propose":
                journal.get(args.identifier)
                identity = local_operator_identity()
                with RecoveryDecisionJournal(settings.database) as decisions:
                    decision_id = decisions.record(
                        intent_id=args.identifier, expected_generation=args.generation,
                        operator_id=identity, proposed_action=args.action,
                        observation=args.observation, rationale=args.rationale)
                result = {"decision_id": decision_id, "recorded_by": identity,
                          "executed": False}
            elif args.operation == "proposals":
                journal.get(args.identifier)
                with RecoveryDecisionJournal(settings.database) as decisions:
                    result = decisions.list_for_intent(args.identifier, limit=args.limit)
            elif args.operation == "assess":
                result = orchestrator_factory(journal).assess_recovery(args.identifier)
            else:
                # Observation only: no automatic or implicit DNS retry.
                intent = orchestrator_factory(journal).reconcile(args.identifier, retry=False)
                result = describe(intent)
    except UnknownIntent:
        print("intent not found", file=sys.stderr)
        return 3
    except (UpdateConflict, PermissionDenied) as exc:
        print(f"operation refused: {exc}", file=sys.stderr)
        return 4
    except (ValueError, PermissionError) as exc:
        print(f"operation refused: {exc}", file=sys.stderr)
        return 4
    except (OSError, TimeoutError, DNSException) as exc:
        print(f"authoritative observation unavailable: {type(exc).__name__}", file=sys.stderr)
        return 5
    print(json.dumps(result, sort_keys=True, indent=2))
    if args.operation == "reconcile" and result["state"] != "applied":
        return 6
    return 0


if __name__ == "__main__":
    sys.exit(main())
