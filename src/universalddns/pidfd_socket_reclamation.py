"""Linux pidfd evidence for supervised socket reclamation.

The supervisor must bind each pidfd to a known socket-descriptor holder while
that process is alive; checking pidfds cannot discover unknown inherited FDs.
"""
import os
import select

from .trusted_socket_reclamation import reclaim_preserved_socket


def _require_exited_pidfd(expected_pid: int, pidfd: int) -> None:
    """Fail closed unless a pinned Linux pidfd names an exited process."""
    if (type(expected_pid) is not int or expected_pid <= 0
            or type(pidfd) is not int or pidfd < 0
            or not hasattr(os, "pidfd_open")):
        raise ValueError("listener exit unverified")
    try:
        with open(f"/proc/self/fdinfo/{pidfd}", encoding="ascii") as record:
            fields = [line.split(":", 1)[1].strip() for line in record
                      if line.startswith("Pid:")]
        if len(fields) != 1 or fields[0] != str(expected_pid):
            raise ValueError("listener exit unverified")
        watcher = select.poll()
        watcher.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        events = watcher.poll(0)
        if (not events or not any(mask & select.POLLIN for _, mask in events)
                or any(mask & (select.POLLNVAL | select.POLLERR)
                       for _, mask in events)):
            raise ValueError("listener exit unverified")
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("listener exit unverified") from exc


def reclaim_exited_listener_socket(parent, expected_identity: tuple[int, int], *,
                                  expected_pid: int, listener_pidfd: int,
                                  writer_exclusion_established: bool = False,
                                  additional_holder_pidfds: tuple[tuple[int, int], ...] = ()) -> bool:
    """Require all declared listener-descriptor holders to have exited.

    The optional holders are (expected PID, pinned pidfd) pairs recorded by an
    external supervisor. This check does not discover unknown holders or
    independently enforce directory writer exclusion.
    """
    if not writer_exclusion_established:
        raise ValueError("writer exclusion required")
    _require_exited_pidfd(expected_pid, listener_pidfd)
    if not isinstance(additional_holder_pidfds, tuple):
        raise ValueError("listener exit unverified")
    for holder in additional_holder_pidfds:
        if (not isinstance(holder, tuple) or len(holder) != 2):
            raise ValueError("listener exit unverified")
        _require_exited_pidfd(holder[0], holder[1])
    return reclaim_preserved_socket(
        parent, expected_identity,
        writer_exclusion_established=writer_exclusion_established)
