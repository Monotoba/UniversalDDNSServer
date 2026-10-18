# Externally anchored snapshot freshness gate

Status: **isolated only, not authenticated or deployed**.

`require_fresh_snapshot` compares the generation read from a validated snapshot with a separately **trusted** generation and the age of an externally recorded issuance event measured using `time.monotonic()`. The default and maximum permitted age is 300 seconds. It fails closed on missing generation, incorrect generation, future issuance, expiry, invalid clock values, negative/inconsistent counts and invalid limits. The snapshot's `created_at` and filesystem mtime are deliberately **not** used as freshness evidence.

**Critical limit:** this function cannot authenticate the trust inputs. A caller must obtain generation and issuance time from an authorized publisher/observer, in the same monotonic clock domain and boot session. A forged, stale, or client-provided issuance record defeats the contract. Cross-host monotonic timestamps and timestamps persisted across reboot are invalid. The producer, broker and reader are **not** wired to this helper. There is no signed manifest, durable trust anchor, or restart/reboot freshness proof. A future design must fail closed if the authoritative issuance record disappears.

No existing VM, service, ACL, broker method or release is changed.
