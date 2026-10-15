# Local managed-record administration (v0.4 development)

The new local-only `universalddns.record_admin` CLI creates, lists, and revises **inactive** record templates in SQLite. All operations require the host POSIX account to pass the existing `universalddns-operators` group check. It does not start a web administration service or publish DNS records.

Example, run as an authorized non-root OS account on an isolated test host:

```sh
python -m universalddns.record_admin --config /etc/universalddns/config.json create lab --name lab.example.test --type A --ttl 120 --address 192.0.2.41
python -m universalddns.record_admin --config /etc/universalddns/config.json list
python -m universalddns.record_admin --config /etc/universalddns/config.json update lab --name lab.example.test --type A --ttl 300 --address 192.0.2.42 --revision 1
```

The CLI rejects record identifiers or DNS RRsets reserved by static configuration, validates name/zone/type/TTL/IP using `RecordSet`, and requires an expected revision for edits. Competing edits with an outdated revision are refused.

**Important:** these catalog entries are not activated or added to token scopes. Existing configuration-backed API/worker operations are unchanged. Creating a record here does not make it available via `GET /api/v1/records` and does not update authoritative DNS. Activating catalog records with explicit authorization and consistent API/worker visibility is a separate, future feature. Keep the database and parent directory restricted to trusted accounts; this is experimental loopback-only software.
