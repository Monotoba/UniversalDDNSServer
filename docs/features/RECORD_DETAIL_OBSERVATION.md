# Record details and authoritative DNS observation (experimental)

PR #167 adds a read-only `GET /api/v1/records/{record_id}` endpoint with existing
`intents:read` bearer authentication. Only active records currently visible
to the requesting principal can be inspected. Unauthorized record IDs return
404. The response includes record ID, zone, name, type and TTL.

The `authoritative.status` field defaults to `unavailable`. An optional
server-side `record_observer` callback may report `matches_template`,
`differs_from_template`, or `absent`. Observation errors yield `unavailable`,
never `absent`; no observed addresses, backend errors or secrets are returned.
The regular runtime **does not yet configure an observation callback**, so
the initial dashboard correctly displays `unavailable` instead of claiming
to have independently checked live authoritative DNS.

Template matching compares the configured template RRset to a read-only
backend observation, **not** a specific update intent's desired address.
An `applied` journal state is not a fresh authoritative lookup. The dashboard
does not infer publication success from those states.

No new write permissions, remote-access interfaces, deployments or database
migrations are introduced.
