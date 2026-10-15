# Read-only staged record discovery

The runtime now supplies the authenticated `GET /api/v1/records` endpoint with a fresh SQLite snapshot combining configured templates, staged-active catalog records, and the current token-grant inventory. A record only appears if it is staged active and its record ID is included in the requesting token's explicit grants. The read-only endpoint does not include address values or credential digests.

**Write operations remain unchanged.** `PUT /api/v1/records/{record_id}/address`, DynDNS2 updates, intent-status checks, and publication-worker authorization continue to use the static configured record mapping. A catalog record appearing in discovery is not yet eligible for DNS writes or publication. This is experimental development functionality, not a finished activation feature.

Invalid or stale grants are rejected by the snapshot validator rather than silently widening access. The remaining implementation milestone must provide a consistent activation and authorization protocol for intake, worker and in-flight updates, including revocation.
