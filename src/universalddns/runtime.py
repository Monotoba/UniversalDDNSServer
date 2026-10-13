"""Pre-alpha local deployment entry points. Not intended for public exposure."""
import argparse
import json
import os
import signal
import stat
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from .adapters.rfc2136 import RFC2136Backend, RFC2136Config
from .adapters.sqlite_intents import SQLiteIntentJournal
from .domain import RecordSet
from .http_api import create_app
from .orchestrator import UpdateOrchestrator
from .token_store import TokenStore
from .worker import PublicationWorker


@dataclass(frozen=True)
class Settings:
    database: Path
    credentials: Path
    records: dict[str, RecordSet]
    dns: RFC2136Config
    interval: float


def load_settings(config_path: str | Path) -> Settings:
    path = Path(config_path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {"database", "credentials", "records", "dns", "interval"}:
        raise ValueError("unexpected or missing configuration keys")
    database = Path(data["database"])
    credentials = Path(data["credentials"])
    if not database.is_absolute() or not credentials.is_absolute():
        raise ValueError("database and credentials paths must be absolute")
    if not credentials.is_file():
        raise ValueError("DNS credential file missing")
    if credentials.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise PermissionError("credential file must not grant group or other access")
    secret = json.loads(credentials.read_text(encoding="utf-8"))
    if set(secret) != {"key_secret"}:
        raise ValueError("credential file must contain only key_secret")
    dns_fields = data["dns"]
    if set(dns_fields) != {"zone", "server", "key_name", "port"}:
        raise ValueError("unexpected DNS configuration fields")
    dns = RFC2136Config(**dns_fields, key_secret=secret["key_secret"])
    if not isinstance(data["records"], dict) or not data["records"]:
        raise ValueError("records must be a nonempty object")
    records = {}
    for identifier, item in data["records"].items():
        if not identifier or not isinstance(item, dict):
            raise ValueError("invalid record identifier")
        if set(item) != {"name", "type", "ttl", "address"}:
            raise ValueError("invalid record configuration")
        rrset = RecordSet(dns.zone, item["name"], item["type"],
                          item["ttl"], (item["address"],))
        records[identifier] = rrset
    interval = data["interval"]
    if type(interval) not in (int, float) or not 0.1 <= interval <= 3600:
        raise ValueError("interval must be 0.1 to 3600 seconds")
    return Settings(database, credentials, records, dns, float(interval))


class Policy:
    def __init__(self, settings: Settings):
        self.records = settings.records

    def may_update(self, principal_id, rrset):
        # Authorization is deliberately checked against live credential scopes.
        with TokenStore(self.database) as store:
            return any(p.identifier == principal_id
                       and "records:write" in p.scopes
                       and any(rid in p.record_ids and template.key == rrset.key
                               for rid, template in self.records.items())
                       for p in store.principals())

    @classmethod
    def for_settings(cls, settings: Settings):
        policy = cls(settings)
        policy.database = settings.database
        return policy


def factories(settings: Settings):
    def journal():
        return SQLiteIntentJournal(settings.database)

    def orchestrator(instance):
        return UpdateOrchestrator(Policy.for_settings(settings), instance,
                                  RFC2136Backend(settings.dns))

    def principals():
        with TokenStore(settings.database) as store:
            return store.principals()

    return journal, orchestrator, principals


def api_app():
    settings = load_settings(os.environ["UNIVERSALDDNS_CONFIG"])
    journal, orchestrator, principals = factories(settings)
    return create_app(journal, orchestrator, settings.records, principals)


def main():
    parser = argparse.ArgumentParser(description="UniversalDDNSServer local worker")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    settings = load_settings(args.config)
    journal, orchestrator, _ = factories(settings)
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    with journal() as instance:
        PublicationWorker(instance, orchestrator(instance)).serve(
            stop, journal, orchestrator, interval_seconds=settings.interval
        )


if __name__ == "__main__":
    main()
