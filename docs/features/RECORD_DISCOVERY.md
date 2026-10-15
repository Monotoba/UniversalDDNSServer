# Record discovery (v0.4 development)

`GET /api/v1/records` provides authenticated discovery of server-managed DNS record templates. Use a bearer token with the `intents:read` scope. Results are filtered by the record IDs allowed for that token and sorted by record ID. The response includes record ID, canonical DNS name, address family (`A` or `AAAA`), and TTL. It does not expose credentials or the configured initial address.

```sh
curl -fsS -H "Authorization: Bearer $DDNS_TOKEN" http://127.0.0.1:8765/api/v1/records
```

A missing or invalid token returns HTTP 401; insufficient scope returns 403. An authorized token with no matching records returns `{"records":[]}`. The existing update endpoint continues to require `records:write`; record discovery does not confer write permission.

This is the first multi-record management increment. Records are still defined in the local server configuration; dynamic creation, editing, deletion, and durable record definitions are not implemented yet. The HTTP listener remains experimental and loopback-only; do not expose it to the public internet.
