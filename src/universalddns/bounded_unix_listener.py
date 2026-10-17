"""Isolated nonblocking Unix listener with bounded *accepted* connections.

This is a disposable fixture, not a production IPC service. Pending kernel
connections may exist in the listen backlog; only accepted sockets are capped.
"""
import selectors
import socket
from contextlib import contextmanager
from collections.abc import Iterator


class BoundedUnixListener:
    def __init__(self, listener: socket.socket, *, max_active: int = 2):
        if type(max_active) is not int or not 1 <= max_active <= 64:
            raise ValueError("snapshot unavailable")
        if listener.family != socket.AF_UNIX or listener.type & socket.SOCK_STREAM == 0:
            raise ValueError("snapshot unavailable")
        self.listener = listener
        self.max_active = max_active
        self._active: set[socket.socket] = set()

    @property
    def active_count(self) -> int:
        return len(self._active)

    def accept(self, *, timeout: float = 0.5) -> socket.socket:
        """Admit one ready peer; reject excess without retaining its FD."""
        if self.listener.fileno() < 0 or not 0 < timeout <= 5:
            raise ValueError("snapshot unavailable")
        with selectors.DefaultSelector() as selector:
            selector.register(self.listener, selectors.EVENT_READ)
            if not selector.select(timeout):
                raise ValueError("snapshot unavailable")
        try:
            channel, _ = self.listener.accept()
        except OSError as exc:
            raise ValueError("snapshot unavailable") from exc
        if len(self._active) >= self.max_active:
            channel.close()
            raise ValueError("snapshot unavailable")
        channel.settimeout(timeout)
        self._active.add(channel)
        return channel

    def release(self, channel: socket.socket) -> None:
        """Close exactly the accepted socket owned by this listener."""
        if channel not in self._active:
            raise ValueError("snapshot unavailable")
        self._active.remove(channel)
        channel.close()

    @contextmanager
    def admitted(self, *, timeout: float = 0.5) -> Iterator[socket.socket]:
        channel = self.accept(timeout=timeout)
        try:
            yield channel
        finally:
            self.release(channel)

    def close(self) -> None:
        for channel in tuple(self._active):
            self.release(channel)
        self.listener.close()
