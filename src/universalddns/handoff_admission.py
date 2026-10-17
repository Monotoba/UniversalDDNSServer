"""Optional process-local, fail-closed admission guard for isolated handoff callers.

Only cooperating callers using this instance are serialized. This cannot
limit other processes, accepted sockets, or a remote uncooperative server.
"""
import threading
from contextlib import contextmanager
from collections.abc import Iterator


class HandoffAdmission:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    @contextmanager
    def admit(self) -> Iterator[None]:
        if not self._lock.acquire(blocking=False):
            raise ValueError("snapshot unavailable")
        try:
            yield
        finally:
            self._lock.release()
