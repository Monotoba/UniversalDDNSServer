# Catalog credential authorization — v0.4 development

This increment adds a fail-closed scope-filtered view for proposed catalog activation. Staging or creating a record **does not** automatically authorize any client to read or update it. `scoped_records` intersects a candidate record mapping with the principal's explicit record IDs and the requested `intents:read` or `records:write` scope.

`validate_catalog_grants` checks that the mapping still includes every configured record without mutation, no two IDs represent the same RRset, and every checked principal grant names a record in the candidate mapping. A mismatched or stale grant is an error, not a reason to widen access.

**Deployment boundary:** These functions are not yet wired into the worker or HTTP API. Dynamic record activation must also account for consistent snapshots across processes, concurrent scope revocation and in-flight updates. Do not use the staged `active` flag to infer real DNS publication or grant new permissions. Existing loopback-only experimental deployment remains unchanged.
