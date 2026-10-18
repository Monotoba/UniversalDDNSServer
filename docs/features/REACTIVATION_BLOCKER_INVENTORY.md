# Inspecting credentials that block record reactivation

The local operator can inspect the credentials preventing a catalog record from being staged active, without handling bearer tokens or digest hashes:

```sh
sudo -u ubuntu /opt/universalddns/venv/bin/python -m universalddns.record_admin \
  --config /etc/universalddns/config.json blockers RECORD_ID
```

Run as an OS account already authorized for local record administration (the example assumes `ubuntu` has been granted operator membership). The output lists principal names, each credential's explicit scopes and record-ID grants, plus the number of **active credentials** blocking reactivation. Multiple credentials for one principal count separately. The command does not revoke credentials, issue new tokens or publish DNS.

To remove a blocker, use the existing local token revocation flow with the bearer token supplied securely on standard input. The inventory intentionally omits tokens and hashes, so operators who no longer have a token cannot selectively revoke it through this CLI. Do not mistake the inventory for a revocation mechanism. Recheck the blocker count before staging reactivation.
