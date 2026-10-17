"""Optional Linux process-lifetime check for isolated descriptor transfers.

A parent pins the expected process using os.pidfd_open while it is alive.
The pidfd belongs to the caller; this helper never closes it.
"""
import os
import select
import socket

from .snapshot_handoff import peer_credentials


def require_live_peer_pidfd(
    channel: socket.socket, *, expected_pid: int, pidfd: int,
) -> None:
    """Fail closed on an exited peer or a mismatched pinned process."""
    if (type(expected_pid) is not int or expected_pid <= 0
            or type(pidfd) is not int or pidfd < 0
            or not hasattr(os, "pidfd_open")):
        raise ValueError("handoff unavailable")
    try:
        if peer_credentials(channel)[0] != expected_pid:
            raise ValueError("handoff unavailable")
        # Linux fdinfo exposes the PID identity pinned by a pidfd. Checking
        # this prevents a pidfd for another live process from being supplied.
        with open(f"/proc/self/fdinfo/{pidfd}", encoding="ascii") as record:
            lines = record.readlines()
        fields = [line.split(":", 1)[1].strip()
                  for line in lines if line.startswith("Pid:")]
        if len(fields) != 1 or fields[0] != str(expected_pid):
            raise ValueError("handoff unavailable")
        watcher = select.poll()
        watcher.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        if watcher.poll(0):
            raise ValueError("handoff unavailable")
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("handoff unavailable") from exc
