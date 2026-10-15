# Candidate runtime record mapping

The internal `candidate_records(configured, catalog)` helper combines static configured records with staged-active SQLite catalog records. It refuses duplicate record IDs or DNS RRset keys, and rejects a catalog of more than 1,000 staged records rather than silently truncating the candidate set.

**Not yet enabled for publication.** This mapping is a preparation step only. The API, authorization policy, DynDNS2 endpoint and worker must share the same consistent view, with credential record scopes verified against staged entries and appropriate collision/reload handling, before the helper is used for live DNS updates. No records are automatically activated in the running server by this feature.
