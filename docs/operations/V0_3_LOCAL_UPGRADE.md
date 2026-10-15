# v0.3 local installation and migration — experimental only

This procedure covers a **disposable Ubuntu 24.04 loopback-only deployment** upgraded from the published v0.2.0a1 alpha to the current v0.3 development branch. It does not qualify an internet-facing system for production. The existing REST v1 endpoint remains supported. BIND 9 and RFC 2136/TSIG remain independently configured.

## Before changing anything

1. Record the installed revision with `sudo git -C /opt/universalddns/src rev-parse HEAD` and inspect `systemctl status universalddns-api universalddns-worker`.
2. Preserve an independent VM snapshot and a protected SQLite backup. Do not copy only a WAL-mode `state.sqlite3` file while services are writing. The disposable-VM updater stops both services and uses the SQLite backup API.
3. Retain `/etc/universalddns/config.json`, `/etc/universalddns/tsig.json`, the database and issued client tokens. **Do not reissue credentials or regenerate the database just to enable DynDNS2.**
4. Verify that your managed host mapping is unique: `records.<record_id>.name` must match the requested DynDNS2 hostname. If multiple configured records share the name, the initial compatibility endpoint rejects the ambiguous match.

## Configuration

The existing [server configuration example](../../deploy/config.example.json) remains valid. No `dyndns2` configuration key or database migration is required. The HTTP API provides `GET /nic/update` on the same loopback listener as REST v1.

Issue or reuse a scoped token for one managed record using the [deployment instructions](DEPLOYMENT.md). DynDNS2's HTTP Basic username is ignored; its password is the same issued API token. **Basic authentication over unencrypted HTTP is safe only within the isolated loopback test boundary. Never forward this endpoint to a public interface or send that token across a network.**

For UDDNSUpdater choose either:
- `UniversalDDNSServer` (recommended): `base_url=http://127.0.0.1:8765`, `record_id=home`, `token=<issued-token>`. This REST adapter tracks durable intent identifiers and status.
- `UniversalDDNSDynDNS2` (experimental): `base_url=http://127.0.0.1:8765`, `hostname=home.example.test`, `token=<issued-token>`. The adapter recognizes `good <ip>` and `nochg <ip>`; `911` means the result remains unconfirmed and requires operator review before reattempting.

Set UDDNSUpdater's supported persistent-state options. Neither adapter verifies global propagation. UDDNSUpdater discovers an IPv4 address externally; tests stub that discovery rather than depending on public services. These examples deliberately do not place secrets in the repository.

## Upgrade an already installed disposable VM

On a snapshot-protected VM named `uddns-prealpha`, copy the latest updater to the VM and run:

```sh
ssh ubuntu@VM_IP 'curl -fsSL https://raw.githubusercontent.com/Monotoba/UniversalDDNSServer/main/tests/deployment/update-vm.sh -o ~/update-vm.sh && bash ~/update-vm.sh'
ssh ubuntu@VM_IP 'bash ~/update-vm.sh --verify'
```

Replace `VM_IP` with the existing guest IP. The updater refuses non-VM hosts/unexpected hostnames, dirty or non-fast-forward checkouts, and missing database/services. It stops services, creates an integrity-checked SQLite backup, upgrades the package, restarts both services, and runs host verification. Failure triggers **best-effort** rollback, not transactional rollback. The backup directory is logged. Do not use this script on a production server.

## Post-upgrade checks (read-only)

```sh
ssh ubuntu@VM_IP 'bash ~/update-vm.sh --verify'
ssh ubuntu@VM_IP 'sudo journalctl -u universalddns-api -u universalddns-worker -n 30 --no-pager'
ssh ubuntu@VM_IP 'sudo -u universalddns /opt/universalddns/venv/bin/python -m universalddns.admin --config /etc/universalddns/config.json list'
```

Verify that previously issued credential metadata is present and pre-existing REST intent identifiers remain readable with the same authorized client. The new `/nic/update` handler can be tested without a DNS write by omitting credentials:

```sh
ssh ubuntu@VM_IP 'curl -fsS http://127.0.0.1:8765/nic/update'
```

Expected response: `badauth`. A real authorized update may mutate the disposable DNS zone; execute one only when explicitly intended, then inspect authoritative BIND results.

## Troubleshooting and recovery

- **`badauth`** — token missing, revoked or missing `records:write`; never print or paste tokens into issue reports.
- **`nohost`** — requested hostname not mapped to an authorized record; inspect mapping and scopes.
- **`notfqdn` / `dnserr`** — malformed hostname/IP or wrong address family.
- **`badagent`** — unsupported DynDNS2 query parameters.
- **`911`** — worker has not confirmed completion within the bounded response window, publication failed ambiguously, or rate limiting intervened. Inspect the intent journal and authoritative DNS; **do not blindly retry**.
- **Service startup fails** — inspect journal logs and config permissions, not token values. Retain the updater's backup.
- **REST clients lose access** — verify original token and database are unchanged, and that client host ID still exists.
- **Migration verification fails** — preserve the backup and VM snapshot, stop further writes, review logs and perform only a deliberate restore.

## Test evidence and boundaries

CI includes a SQLite credential/intents preservation regression and end-to-end DynDNS2/REST integration against isolated BIND 9. This is evidence for an additive local upgrade path, **not** proof of real-host migration or complete crash recovery. No new schema migration is introduced for the DynDNS2 endpoint. The released v0.2.0a1 tag and its artifacts remain unchanged.
