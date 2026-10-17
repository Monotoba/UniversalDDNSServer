"""Bounded registry that owns independent Linux pidfd duplicates.

Completeness is still an assertion by a trusted external coordinator.
"""
import os

from .pidfd_socket_reclamation import reclaim_exited_listener_socket


class ListenerHolderRegistry:
    def __init__(self, *, max_holders: int = 8):
        if type(max_holders) is not int or not 1 <= max_holders <= 64:
            raise ValueError("invalid holder capacity")
        self._max_holders = max_holders
        self._holders: dict[int, int] = {}
        self._sealed = False
        self._closed = False

    def register(self, pid: int, pidfd: int) -> None:
        if self._closed:
            raise ValueError("holder registry closed")
        if self._sealed:
            raise ValueError("holder registry sealed")
        if (type(pid) is not int or pid <= 0
                or type(pidfd) is not int or pidfd < 0
                or pid in self._holders or len(self._holders) >= self._max_holders):
            raise ValueError("invalid holder registration")
        try:
            # Validate the supplied kernel pidfd association before duplicating.
            with open(f"/proc/self/fdinfo/{pidfd}", encoding="ascii") as record:
                fields = [line.split(":", 1)[1].strip()
                          for line in record if line.startswith("Pid:")]
            if len(fields) != 1 or fields[0] != str(pid):
                raise ValueError("invalid holder registration")
            owned = os.dup(pidfd)
            try:
                os.set_inheritable(owned, False)
                self._holders[pid] = owned
            except BaseException:
                os.close(owned)
                raise
        except (OSError, ValueError) as exc:
            raise ValueError("invalid holder registration") from exc

    def seal(self) -> None:
        if self._closed:
            raise ValueError("holder registry closed")
        if not self._holders:
            raise ValueError("empty holder registry")
        self._sealed = True

    def reclaim(self, parent, expected_identity: tuple[int, int], *,
                owner_pid: int, writer_exclusion_established: bool = False) -> bool:
        """Require sealed registry and exited owned pidfds for all holders."""
        if self._closed:
            raise ValueError("holder registry closed")
        if not self._sealed or owner_pid not in self._holders:
            raise ValueError("holder registry incomplete")
        others = tuple((pid, fd) for pid, fd in self._holders.items()
                       if pid != owner_pid)
        return reclaim_exited_listener_socket(
            parent, expected_identity, expected_pid=owner_pid,
            listener_pidfd=self._holders[owner_pid],
            additional_holder_pidfds=others,
            writer_exclusion_established=writer_exclusion_established)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._sealed = False
        holders, self._holders = self._holders, {}
        for fd in holders.values():
            os.close(fd)

    def __enter__(self):
        if self._closed:
            raise ValueError("holder registry closed")
        return self

    def __exit__(self, *_):
        self.close()
