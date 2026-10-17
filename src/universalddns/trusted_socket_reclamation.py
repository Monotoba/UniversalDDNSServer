"""Explicit reclamation for isolated, preserved AF_UNIX socket pathnames.

Caller must exclude all other pathname writers and establish listener exit.
Directory mode 0700 cannot exclude another same-UID writer.
"""
import os
import stat
from pathlib import Path


def reclaim_preserved_socket(parent: str | Path, expected_identity: tuple[int, int], *,
                             writer_exclusion_established: bool = False) -> bool:
    """Remove a known stopped socket inside a trusted writer-exclusion window.

    expected_identity is the original (st_dev, st_ino) socket identity.
    Missing entries return False; unsafe or mismatched entries raise ValueError.
    """
    if not writer_exclusion_established:
        raise ValueError("writer exclusion required")
    if (not isinstance(expected_identity, tuple) or len(expected_identity) != 2
            or any(type(v) is not int or v < 0 for v in expected_identity)):
        raise ValueError("invalid socket identity")
    directory = Path(parent)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        pinned = os.fstat(fd)
        named = directory.lstat()
        if (not stat.S_ISDIR(named.st_mode)
                or (named.st_dev, named.st_ino) != (pinned.st_dev, pinned.st_ino)
                or pinned.st_uid != os.geteuid()
                or stat.S_IMODE(pinned.st_mode) != 0o700):
            raise ValueError("untrusted socket directory")
        try:
            endpoint = os.stat("ipc.sock", dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        if (not stat.S_ISSOCK(endpoint.st_mode)
                or endpoint.st_uid != os.geteuid()
                or (endpoint.st_dev, endpoint.st_ino) != expected_identity):
            raise ValueError("socket identity mismatch")
        # The check and unlink are NOT atomic against unexcluded writers.
        os.unlink("ipc.sock", dir_fd=fd)
        return True
    finally:
        os.close(fd)
