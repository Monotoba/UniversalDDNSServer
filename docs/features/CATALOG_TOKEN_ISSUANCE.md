# Issuing a token for a staged-active record

The v0.4 REST publication path supports catalog-managed A/AAAA records, but the local token-administration command must also recognize them. This change permits the existing **local-only** credential CLI to grant explicitly named, staged-active catalog record IDs; inactive, unknown or conflicting records remain ineligible for new grants.

After creating and staging a record using `python -m universalddns.record_admin`, the authorized administrator may issue its token with:

```sh
sudo -u universalddns /opt/universalddns/venv/bin/python -m universalddns.admin \
  --config /etc/universalddns/config.json issue \
  --principal device-1 --record dynamic \
  --scope records:write --scope intents:read
```

**Store the stdout bearer token securely.** Do not paste it into shell history, logs or shared notes. This command remains local-only; it does not add a token issuance HTTP endpoint. Issuance does not publish DNS. The worker still rechecks activation and authorization before publication.

Current operational limitation: previously issued tokens that reference a subsequently deactivated record can cause the current catalog snapshot validator to fail closed for all record discovery/write requests (HTTP 503), until the stale token is revoked or record reactivated. A follow-up design must allow safe record deactivation without creating a global availability problem. Do not perform a live deactivation trial on a shared environment yet.
