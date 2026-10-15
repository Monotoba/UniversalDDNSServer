"""Build collision-checked candidate record mappings for future runtime activation.

This function does not grant token scopes or change the API/worker routing.
"""
from .domain import RecordSet
from .record_catalog import RecordCatalog


def candidate_records(configured: dict[str, RecordSet],
                      catalog: RecordCatalog) -> dict[str, RecordSet]:
    """Combine configured templates with staged catalog entries, fail closed.

    Callers MUST separately validate principal scopes and use a consistent
    mapping across authorization, intake and publication.
    """
    combined = dict(configured)
    keys = {item.key for item in configured.values()}
    # Iterate bounded pages only when the catalog becomes paginable. Until
    # then, fail closed rather than silently omitting staged records.
    rows = catalog._db.execute(
        "SELECT COUNT(*) FROM managed_records WHERE active=1"
    ).fetchone()[0]
    if rows > 1000:
        raise ValueError("too many staged records for candidate mapping")
    for record_id, rrset, _revision in catalog.active_records(limit=1000):
        if record_id in combined or rrset.key in keys:
            raise ValueError("staged record conflicts with configured or catalog RRset")
        combined[record_id] = rrset
        keys.add(rrset.key)
    return combined
