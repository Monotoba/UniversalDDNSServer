# Safe dormant grants after record deactivation

Token grants are durable and may outlive activation of a catalog-managed record. A deactivated record must not cause unrelated clients' record discovery and updates to return HTTP 503 merely because its ID remains in a token.

The snapshot validator now checks configured IDs/RRset integrity but does not reject token IDs absent from the *active* mapping. Endpoints and worker authorization still intersect each client's explicit grants with the active mapping. An inactive record therefore cannot receive new intents, and a pending intent fails the worker's authorization check after deactivation.

Unknown IDs cannot be newly granted using the local token issuance command, which validates the current active mapping. Previously stored dormant grants remain stored and can regain authority if the same record ID is reactivated. Operators should revoke grants if that is undesirable; this change does not automatically revoke credentials or cancel an already-issued DNS write. RFC 2136 publication still has a check-to-write race, and no production DNS fencing is claimed.
