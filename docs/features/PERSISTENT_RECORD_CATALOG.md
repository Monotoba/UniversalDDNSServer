# Durable managed record catalog — v0.4 development

The new internal `RecordCatalog` stores explicitly managed A/AAAA record definitions in SQLite with a unique record identifier, unique DNS RRset key, validated TTL/addresses and an incrementing revision. A caller can create, list and retrieve catalog entries; replacing an entry requires the expected revision, so a stale editor is rejected.

**Activation boundary:** This first increment does **not** replace the `records` dictionary loaded from `config.json`. The HTTP API, DNS worker and token authorization continue using the original static configuration. This prevents a catalog entry from inadvertently gaining publication authority, bypassing client scopes or changing a live record during migration.

The next feature increments should introduce a deliberately authenticated admin API, checked record activation, consistent worker/API catalog access, and safe retention of old configured IDs and token scopes. Do not directly edit SQLite entries or grant unreviewed privileges to catalog writers.

`RecordCatalog.create(record_id, rrset)`, `get(record_id)`, `list_records(limit=100)`, and `update(record_id, rrset, expected_revision=...)` are internal interfaces. They are not currently HTTP endpoints or a supported operator CLI.
