"""Structured, bounded audit events. Never include bearer tokens or TSIG material."""
import json
import logging
import re

_logger = logging.getLogger("universalddns.audit")
_SAFE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def audit(event: str, **fields: str) -> None:
    """Emit one JSON object with an allowlisted event and redacted scalar fields."""
    if not _SAFE.fullmatch(event):
        raise ValueError("invalid audit event")
    payload = {"event": event}
    for key, value in fields.items():
        if not _SAFE.fullmatch(key):
            raise ValueError("invalid audit field")
        if not isinstance(value, str):
            raise TypeError("audit fields must be strings")
        payload[key] = value if _SAFE.fullmatch(value) else "[redacted]"
    _logger.info("%s", json.dumps(payload, sort_keys=True, separators=(",", ":")))
