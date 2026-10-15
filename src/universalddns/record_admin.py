"""Local privileged management of inactive, durable DNS record templates."""
import argparse
import json
import sys

from .domain import RecordSet
from .local_operator import local_operator_identity
from .record_catalog import RecordCatalog
from .runtime import load_settings


def main():
    parser = argparse.ArgumentParser(description="Manage inactive DNS record templates")
    parser.add_argument("--config", required=True)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("list")
    stage = sub.add_parser("stage", help="Set catalog activation flag; does not publish DNS")
    stage.add_argument("record_id")
    stage.add_argument("--revision", required=True, type=int)
    stage.add_argument("--active", choices=("yes", "no"), required=True)
    for name in ("create", "update"):
        cmd = sub.add_parser(name)
        cmd.add_argument("record_id")
        cmd.add_argument("--name", required=True)
        cmd.add_argument("--type", choices=("A", "AAAA"), required=True)
        cmd.add_argument("--ttl", required=True, type=int)
        cmd.add_argument("--address", required=True)
        if name == "update":
            cmd.add_argument("--revision", required=True, type=int)
    args = parser.parse_args()
    try:
        operator = local_operator_identity()
        settings = load_settings(args.config)
        with RecordCatalog(settings.database) as catalog:
            if args.operation == "list":
                result = {"records": [
                    {"id": identifier, "name": rr.name, "type": rr.record_type,
                     "ttl": rr.ttl, "addresses": list(rr.values), "revision": revision}
                    for identifier, rr, revision in catalog.list_records()
                ]}
            elif args.operation == "stage":
                if args.record_id in settings.records:
                    raise ValueError("record ID reserved by static configuration")
                existing = catalog.get(args.record_id)
                if existing is None:
                    raise ValueError("record not found")
                if any(rr.key == existing[0].key for rr in settings.records.values()):
                    raise ValueError("RRset reserved by static configuration")
                revision = catalog.set_active(args.record_id,
                                              expected_revision=args.revision,
                                              active=args.active == "yes")
                result = {"id": args.record_id, "revision": revision,
                          "staged_active": args.active == "yes",
                          "runtime_active": False, "recorded_by": operator}
            else:
                if args.record_id in settings.records:
                    raise ValueError("record ID is reserved by static configuration")
                rr = RecordSet(settings.dns.zone, args.name, args.type,
                               args.ttl, (args.address,))
                if any(existing.key == rr.key for existing in settings.records.values()):
                    raise ValueError("DNS RRset is reserved by static configuration")
                if args.operation == "create":
                    revision = catalog.create(args.record_id, rr)
                else:
                    revision = catalog.update(args.record_id, rr,
                                              expected_revision=args.revision)
                result = {"id": args.record_id, "revision": revision,
                          "recorded_by": operator, "active": False}
    except (ValueError, TypeError, PermissionError) as exc:
        print(f"operation refused: {exc}", file=sys.stderr)
        return 4
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
