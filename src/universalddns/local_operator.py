"""Local-only privileged operator identity for recovery decision proposals."""
import os
import pwd


def local_operator_identity() -> str:
    """Resolve the effective POSIX user, rejecting root and impersonation.

    Authentication is delegated to the host OS: only trusted users granted
    database write access may record proposals. Never accept a --user override.
    """
    if os.name != "posix":
        raise PermissionError("POSIX local operator identity required")
    uid = os.getuid()
    euid = os.geteuid()
    if uid == 0 or euid == 0 or uid != euid:
        raise PermissionError("root or changed effective UID is not an operator identity")
    identity = pwd.getpwuid(euid).pw_name
    if not identity or len(identity) > 128 or not identity.isascii() or not all(
        c.isalnum() or c in "-_." for c in identity
    ):
        raise PermissionError("unsupported local operator identity")
    return identity
