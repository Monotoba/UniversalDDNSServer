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

Before starting services, verify that the service account can read the credential file and write the state directory, the BIND TSIG key can modify **only** intended records, and `/etc/universalddns/tsig.json` is not a symlink. Verify both unit files with `systemd-analyze verify`. The integration CI covers Python 3.11–3.13, but a fresh-host Ubuntu installation, reboot persistence, package upgrades, backup restoration, and actual systemd activation are separate manual release gates.

## Local acceptance checks

Run `deploy/smoke-check.sh` from the checkout after the API service starts. It checks loopback liveness and confirms that an unauthenticated intent query returns HTTP 401. This smoke check **does not modify DNS** and is not a substitute for a host systemd installation test. Verify systemd unit syntax with `systemd-analyze verify` and inspect `systemctl status universalddns-api universalddns-worker` on the target machine. To verify actual publication, use a disposable test zone and confirm the intended A/AAAA RRset directly at its authoritative nameserver. Do not run this against live production zones.

## Limitations

No production TLS reverse-proxy guide or security approval exists, and systemd deployment itself has not been exercised on a real installed host. The process-local rate limiter does not provide distributed throttling; worker backoff, audit retention, mature credentials handling, and a safe policy for competing authoritative writers are incomplete. Test SQLite backups and restore separately. The DNS operation may succeed even if the worker fails to record completion, requiring authoritative reconciliation. Do not use a residential IP as the sole public authoritative DNS infrastructure. DDNS records do not resolve CGNAT or firewall ingress constraints.
