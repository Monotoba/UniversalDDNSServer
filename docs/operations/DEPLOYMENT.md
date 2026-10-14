# Local Linux deployment — pre-alpha

This is an **experimental loopback-only installation**, not a production or internet-facing deployment. BIND 9 (or an RFC 2136-compatible authoritative DNS server) remains a separately configured dependency. The optional first-party authoritative DNS server is future work.

## Prerequisites

Ubuntu 24.04 or comparable Linux distribution, Python 3.11+, a reachable authoritative DNS server, and an RFC 2136 TSIG key restricted on that server to the intended names and record types. Keep the HTTP API listening on 127.0.0.1; **do not forward it or expose it publicly**. Review the TSIG server update policy separately.

## Installation example (run commands as an administrator)

```sh
sudo useradd --system --home-dir /var/lib/universalddns --shell /usr/sbin/nologin universalddns
sudo install -d -m 0750 -o universalddns -g universalddns /var/lib/universalddns
sudo install -d -m 0700 -o universalddns -g universalddns /etc/universalddns
sudo install -d -m 0755 /opt/universalddns
# Copy a trusted checkout of this repository to /opt/universalddns/src
sudo python3 -m venv /opt/universalddns/venv
sudo /opt/universalddns/venv/bin/pip install '/opt/universalddns/src[api]'
sudo install -m 0600 -o universalddns -g universalddns /opt/universalddns/src/deploy/config.example.json /etc/universalddns/config.json
```

Edit `/etc/universalddns/config.json` to set the authoritative zone, server, port, records, and SQLite database location. Configure the `credentials` field to point to `/etc/universalddns/tsig.json`, and create that file as owner `universalddns` with mode `0600`. Its sole JSON property is `key_secret`, containing the TSIG secret in base64. Never commit this file. Check zone permissions and keys before running either service.

To issue a scoped client token, run the local admin command as the service account, capturing stdout securely (avoid terminal session logging and shell history). The issued token is displayed **once**:

```sh
sudo -u universalddns /opt/universalddns/venv/bin/python -m universalddns.admin \
  --config /etc/universalddns/config.json issue --principal client1 \
  --record home --scope records:write --scope intents:read
```

To revoke a token, pipe it into the local admin command with `revoke --token-stdin`. Do not pass bearer secrets as command-line arguments. Avoid persisting plaintext tokens in scripts.

Install `deploy/universalddns-api.service` and `deploy/universalddns-worker.service` into `/etc/systemd/system/`, then run `systemctl daemon-reload`. For a controlled local experiment, enable and start the API and worker separately. Inspect service logs using `journalctl -u universalddns-api` and `journalctl -u universalddns-worker`. The API binds only to 127.0.0.1:8765; the worker runs independently.

## Security and deployment checklist

The publishing worker rechecks the principal's **current** record-write authorization before it publishes a pending intent; revoking the final eligible token before a worker claims that intent causes it to fail without a DNS write. Revocation cannot cancel an update already in flight. A principal with another valid credential granting access remains authorized. Review revocation behavior and the distinction between `failed` and ambiguous DNS outcomes before operating a deployment.

Before starting services, verify that the service account can read the credential file and write the state directory, the BIND TSIG key can modify **only** intended records, and `/etc/universalddns/tsig.json` is not a symlink. Verify both unit files with `systemd-analyze verify`. The integration CI covers Python 3.11–3.13, and the Ubuntu 24.04.5 VM installation, reboot and offline restoration have been verified. Package upgrades and real-world ambiguous DNS transport failures remain outside validated scope.

## Local acceptance checks

Run `deploy/smoke-check.sh` from the checkout after the API service starts. It checks loopback liveness and confirms that an unauthenticated intent query returns HTTP 401. This smoke check **does not modify DNS** and is not a substitute for a host systemd installation test. Verify systemd unit syntax with `systemd-analyze verify` and inspect `systemctl status universalddns-api universalddns-worker` on the target machine. To verify actual publication, use a disposable test zone and confirm the intended A/AAAA RRset directly at its authoritative nameserver. Do not run this against live production zones.

## Installed-host validation

After installing the systemd units, provisioning a token (which initializes the SQLite database), and starting both services, execute the included host checks:

```sh
sudo sh /opt/universalddns/src/deploy/validate-install.sh
```

The script verifies installed executables, parses both systemd units, confirms that the API and worker units are active, validates the service account's access to the configuration, TSIG credential and existing SQLite database, and checks localhost API liveness and authentication rejection. It does not install packages, modify DNS records or test a reboot. It requires `sudo`, `systemctl`, and `systemd-analyze` on an actual systemd host.

Record the Ubuntu release, Python version, command exit status, journal excerpts without secrets, and any service-restart or backup/restore test results before approving a release. CI validates script syntax and systemd unit parsing; it does **not** count as evidence of a clean systemd installation.

## Limitations

No production TLS reverse-proxy guide or security approval exists. A disposable Ubuntu VM was tested, but production deployment has not been evaluated. The process-local rate limiter does not provide distributed throttling; worker backoff, audit retention, mature credentials handling, and a safe policy for competing authoritative writers are incomplete. Test SQLite backups and restore separately. The DNS operation may succeed even if the worker fails to record completion, requiring authoritative reconciliation. Do not use a residential IP as the sole public authoritative DNS infrastructure. DDNS records do not resolve CGNAT or firewall ingress constraints.

## Local intent inspection and reconciliation (post-v0.1.0a1 development)

The local operator CLI can inspect queued, applying, and failed intents without using the HTTP API. Run it as the dedicated service account on the server:

```sh
sudo -u universalddns /opt/universalddns/venv/bin/python -m universalddns.operator \
  --config /etc/universalddns/config.json list --state failed --limit 50
sudo -u universalddns /opt/universalddns/venv/bin/python -m universalddns.operator \
  --config /etc/universalddns/config.json show INTENT_UUID
sudo -u universalddns /opt/universalddns/venv/bin/python -m universalddns.operator \
  --config /etc/universalddns/config.json reconcile INTENT_UUID
```

The reconcile command **observes the authoritative DNS state**. It marks a failed or interrupted intent applied only when the observed RRset matches the intended RRset. It **never automatically retries** a DNS write. A nonmatching observation leaves the intent unresolved. Reconciliation can raise an error for actively leased intents, missing identifiers, or unavailable DNS. Output is JSON and may contain hostnames, principal IDs, intended IP addresses, and backend error names; keep it in protected operational logs.

These commands are development features after the v0.1.0a1 release. The existing installed wheel will not have them unless the package is upgraded in a controlled environment.

## Structured audit events (development after v0.1.0a1)

The API and worker emit single-line JSON records through the `universalddns.audit` logger. Events include rejected authentication, insufficient scope, rate-limit denial, accepted submission, publication start/success/failure, and reconciliation results. Only approved short scalar fields (intent IDs, record IDs, principal labels, and error class names) are emitted. Unsafe or unexpected field values are redacted; bearer tokens, full request bodies and TSIG credentials are never passed to the audit emitter.

Inspect locally with `sudo journalctl -u universalddns-api -u universalddns-worker --since today`. Journald persistence, retention limits, collection permissions and centralized export are **operator responsibilities**; this is not a durable, tamper-resistant audit database. Audit events from multiple processes are not globally ordered, and an abrupt crash may prevent some events from being written. Do not rely on audit lines alone as proof of authoritative DNS publication.
