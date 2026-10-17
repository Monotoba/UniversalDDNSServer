"""Bounded, explicitly sealed registry of externally identified listener FD holders.

A seal is a coordinator assertion of completeness, not discovery of holders.
The registry borrows pidfds and does not own or close them.
"""
from .pidfd_socket_reclamation import reclaim_exited_listener_socket


class ListenerHolderRegistry:
    def __init__(self, *, max_holders: int = 8):
        if type(max_holders) is not int or not 1 <= max_holders <= 64:
            raise ValueError("invalid holder capacity")
        self._max_holders = max_holders
        self._holders: dict[int, int] = {}
        self._sealed = False

    def register(self, pid: int, pidfd: int) -> None:
        if self._sealed:
            raise ValueError("holder registry sealed")
        if (type(pid) is not int or pid <= 0
                or type(pidfd) is not int or pidfd < 0
                or pid in self._holders or len(self._holders) >= self._max_holders):
            raise ValueError("invalid holder registration")
        self._holders[pid] = pidfd

    def seal(self) -> None:
        if not self._holders:
            raise ValueError("empty holder registry")
        self._sealed = True

    def reclaim(self, parent, expected_identity: tuple[int, int], *,
                owner_pid: int, writer_exclusion_established: bool = False) -> bool:
        """Require sealed registry and exited pidfds for all declared holders."""
        if not self._sealed or owner_pid not in self._holders:
            raise ValueError("holder registry incomplete")
        others = tuple((pid, fd) for pid, fd in self._holders.items()
                       if pid != owner_pid)
        return reclaim_exited_listener_socket(
            parent, expected_identity, expected_pid=owner_pid,
            listener_pidfd=self._holders[owner_pid],
            additional_holder_pidfds=others,
            writer_exclusion_established=writer_exclusion_established)
