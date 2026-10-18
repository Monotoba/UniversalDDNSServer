"""Pre-alpha local deployment entry points. Not intended for public exposure."""
import argparse
import json
import logging
import os
import signal
import stat
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from .adapters.rfc2136 import RFC2136Backend, RFC2136Config
from .adapters.sqlite_intents import SQLiteIntentJournal
from .domain import RecordSet, canonical_name
from .http_api import create_app
from .orchestrator import UpdateOrchestrator
from .record_snapshot import catalog_snapshot
from .record_catalog import RecordCatalog
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
    if database.is_symlink() or credentials.is_symlink():
        raise ValueError("database and credential symlinks are not supported")
    if not database.parent.is_dir():
        raise ValueError("database parent directory must exist")
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


@dataclass(frozen=True)
class AdminSettings:
    """Non-publishing configuration; never load TSIG key material."""
    database: Path
    records: dict[str, RecordSet]
    zone: str


def load_admin_settings(config_path: str | Path) -> AdminSettings:
    """Validate local-admin inputs without opening or stat-ing DNS secrets.

    Administrative commands must still validate record IDs and DNS templates,
    but have no reason to read the authoritative publishing credential.
    """
    data = json.loads(Path(config_path).resolve().read_text(encoding="utf-8"))
    if set(data) != {"database", "credentials", "records", "dns", "interval"}:
        raise ValueError("unexpected or missing configuration keys")
    database = Path(data["database"])
    credentials = Path(data["credentials"])
    if not database.is_absolute() or not credentials.is_absolute():
        raise ValueError("database and credentials paths must be absolute")
    if database.is_symlink() or credentials.is_symlink():
        raise ValueError("database and credential symlinks are not supported")
    if not database.parent.is_dir():
        raise ValueError("database parent directory must exist")
    dns_fields = data["dns"]
    if not isinstance(dns_fields, dict) or set(dns_fields) != {
        "zone", "server", "key_name", "port"
    }:
        raise ValueError("unexpected DNS configuration fields")
    # Check nonsecret DNS configuration without creating an RFC2136Config
    # (which requires actual key material).
    from ipaddress import ip_address
    ip_address(dns_fields["server"])
    if not isinstance(dns_fields["key_name"], str) or not dns_fields["key_name"]:
        raise ValueError("TSIG key name required")
    port = dns_fields["port"]
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid DNS port")
    zone = canonical_name(dns_fields["zone"])
    if not isinstance(data["records"], dict) or not data["records"]:
        raise ValueError("records must be a nonempty object")
    records = {}
    for identifier, item in data["records"].items():
        if not identifier or not isinstance(item, dict):
            raise ValueError("invalid record identifier")
        if set(item) != {"name", "type", "ttl", "address"}:
            raise ValueError("invalid record configuration")
        records[identifier] = RecordSet(
            zone, item["name"], item["type"], item["ttl"], (item["address"],)
        )
    interval = data["interval"]
    if type(interval) not in (int, float) or not 0.1 <= interval <= 3600:
        raise ValueError("interval must be 0.1 to 3600 seconds")
    return AdminSettings(database=database, records=records, zone=zone)


class Policy:
    def __init__(self, settings: Settings):
        self.records = settings.records

    def may_update(self, principal_id, rrset):
        # Refresh BOTH the active catalog and unrevoked grants immediately
        # before each submission or worker publication authorization check.
        with RecordCatalog(self.database):
            pass  # Ensure legacy DBs have the managed_records schema.
        try:
            records, principals = catalog_snapshot(self.database, self.records)
        except (ValueError, KeyError):
            return False  # Fail closed on stale grants or conflicting templates.
        return any(p.identifier == principal_id
                   and "records:write" in p.scopes
                   and any(rid in p.record_ids and template.key == rrset.key
                           for rid, template in records.items())
                   for p in principals)

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
    # Upgrade older static-only databases before serving catalog-backed requests.
    with RecordCatalog(settings.database):
        pass
    journal, orchestrator, principals = factories(settings)
    def readable_records():
        mapping, _ = catalog_snapshot(settings.database, settings.records)
        return mapping

    # RFC2136Backend.observe makes only bounded authoritative DNS queries;
    # do not expose the publishing backend itself to dashboard routes.
    observer = RFC2136Backend(settings.dns).observe
    return create_app(journal, orchestrator, settings.records, principals,
                      record_reader=readable_records, record_observer=observer)


def main():
    parser = argparse.ArgumentParser(description="UniversalDDNSServer local worker")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
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
