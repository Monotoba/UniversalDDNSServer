# Transaction-consistent candidate record snapshot

`catalog_snapshot(database, configured)` reads all staged-active catalog record templates and all non-revoked token grants inside **one SQLite read transaction**. It rejects identifier/RRset collisions, unknown record grants, and catalogs larger than its bounded maximum. No staged record becomes visible to clients merely because it was created.

This is an internal candidate-view API only; it does not change the live HTTP endpoints or publication worker. SQLite read snapshots cannot by themselves fence in-flight DNS operations or guarantee a previously authorized worker remains authorized after a subsequent revocation. That behavior requires worker-side revalidation and an explicit activation/visibility protocol.

The development checkout may be updated after this increment merges. Do not upgrade the running test VM to enable catalog activation: live activation is not implemented yet.
