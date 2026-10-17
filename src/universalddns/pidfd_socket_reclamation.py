"""Linux pidfd evidence that a separately supervised process has exited.

The supervisor must have pinned the correct listener PID while it was alive.
Process exit does not establish absence of other directory writers.
"""
import os
import select

from .trusted_socket_reclamation import reclaim_preserved_socket


def reclaim_exited_listener_socket(parent, expected_identity: tuple[int, int], *,
                                  expected_pid: int, listener_pidfd: int,
                                  writer_exclusion_established: bool = False) -> bool:
    """Require matching exited pidfd before identity-fenced pathname reclamation.

    The caller separately establishes pidfd-to-listener association, exclusive
    writer control, and lack of surviving listener descendants / inherited FDs.
    """
    if not writer_exclusion_established:
        raise ValueError("writer exclusion required")
    if (type(expected_pid) is not int or expected_pid <= 0
            or type(listener_pidfd) is not int or listener_pidfd < 0
            or not hasattr(os, "pidfd_open")):
        raise ValueError("listener exit unverified")
    try:
        with open(f"/proc/self/fdinfo/{listener_pidfd}", encoding="ascii") as record:
            fields = [line.split(":", 1)[1].strip() for line in record
                      if line.startswith("Pid:")]
        if len(fields) != 1 or fields[0] != str(expected_pid):
            raise ValueError("listener exit unverified")
        watcher = select.poll()
        watcher.register(listener_pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        events = watcher.poll(0)
        if not events or not any(mask & select.POLLIN for _, mask in events):
            raise ValueError("listener exit unverified")
        if any(mask & (select.POLLNVAL | select.POLLERR) for _, mask in events):
            raise ValueError("listener exit unverified")
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("listener exit unverified") from exc
    return reclaim_preserved_socket(
        parent, expected_identity,
        writer_exclusion_established=writer_exclusion_established)
