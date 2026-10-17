# Local read-only management dashboard (experimental)

Open `http://127.0.0.1:8765/dashboard` from the machine running the experimental
loopback-only API. The dashboard is served only to requests whose directly
observed client IP is loopback; it is **not** a remote-administration feature.

Enter an existing token with `intents:read` scope to display the records its
principal is authorized to discover. View the newest 20 update intents owned by your principal for currently
permitted record templates, or enter a known intent UUID to query the
existing owner-restricted intent-status endpoint. History is bounded to 50
rows per request; filtering occurs in SQLite before pagination. A token with
`records:write` is not required; this interface has no mutating controls.
The token stays in the page's password field, is sent only in the Bearer
Authorization header, and is not saved to cookies or browser storage.
Clear the field or close the tab after use. Do not enter tokens on a
machine or browser profile you do not trust.

The API's existing scope and record restrictions remain authoritative; the
dashboard does not list unauthorized records. The existing records endpoint
shows active templates visible to the principal, not inactive catalog
entries. The new `GET /api/v1/intents?limit=20` endpoint requires `intents:read`,
filters by principal and currently authorized active record keys, and returns
only intent ID, record ID, state and creation timestamp (UTC, SQLite format).
The endpoint never returns error contents, DNS values or credentials. Pending means queued and is not proof of DNS
publication. The dashboard does not independently report DNS, database, or
worker health. No new API scopes, credential issuance, administrative
commands, or persistence are introduced.

The page has a restrictive content-security policy, no-store caching,
DOM text-node rendering, and no external assets. Do **not** reverse-proxy
this experimental interface for remote access or configure an untrusted
proxy to appear as a loopback peer. Loopback alone is not a full browser
authorization boundary; cross-origin read protections are enforced by
the browser and existing bearer authentication. Future features must
introduce separately reviewed administration permissions and secure
remote-access design.
