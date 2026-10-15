"""Construct client-visible record sets without broadening token permissions."""
from .domain import RecordSet
from .http_api import APIPrincipal


def scoped_records(records: dict[str, RecordSet], principal: APIPrincipal,
                   *, scope: str) -> dict[str, RecordSet]:
    """Select only explicitly granted IDs after checking the requested scope."""
    if scope not in ("records:write", "intents:read"):
        raise ValueError("unsupported record scope")
    if scope not in principal.scopes:
        return {}
    return {record_id: template for record_id, template in records.items()
            if record_id in principal.record_ids}


def validate_catalog_grants(configured: dict[str, RecordSet],
                            candidate: dict[str, RecordSet],
                            principals: tuple[APIPrincipal, ...]) -> None:
    """Refuse ambiguous mapping/grants before making a candidate view live.

    Staging does not give any client access automatically. Existing credentials
    can only name catalog records through explicit existing record-id scopes.
    """
    if not set(configured).issubset(candidate):
        raise ValueError("configured record was removed from candidate")
    for record_id, item in configured.items():
        if candidate[record_id] != item:
            raise ValueError("configured record changed in candidate")
    if len({record.key for record in candidate.values()}) != len(candidate):
        raise ValueError("duplicate DNS RRset key")
    # Dormant grants may reference deactivated records. Requests authorize
    # against the active mapping, so inactive IDs provide no current access.
