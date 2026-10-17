"""Disposable Unix socket with pinned-directory-relative shutdown cleanup.

Only an owner-controlled private directory is accepted. A directory fd pins
the directory even if its pathname is renamed. Unknown entries are never
unlinked, and the original directory pathname must still name the pinned fd.
"""
import os
import socket
import stat
from pathlib import Path

from .bounded_unix_listener import BoundedUnixListener


class OwnedUnixListener:
    def __init__(self, parent: str | Path, name: str = "ipc.sock", *,
                 cleanup_policy: str = "owned-path"):
        directory = Path(parent)
        if (name != "ipc.sock"
                or cleanup_policy not in ("owned-path", "preserve")):
            raise ValueError("snapshot unavailable")
        self._cleanup_policy = cleanup_policy
        self._directory = directory
        self._name = name
        self._dirfd = None
        self._identity = None
        self.path = directory / name
        self.socket = None
        try:
            self._dirfd = os.open(
                directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
            )
            directory_stat = os.fstat(self._dirfd)
            pathname_stat = directory.lstat()
            self._directory_identity = (directory_stat.st_dev, directory_stat.st_ino)
            if (not stat.S_ISDIR(pathname_stat.st_mode)
                    or (pathname_stat.st_dev, pathname_stat.st_ino) != self._directory_identity
                    or directory_stat.st_uid != os.geteuid()
                    or stat.S_IMODE(directory_stat.st_mode) != 0o700):
                raise ValueError("snapshot unavailable")
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.bind(str(self.path))
            self.socket.listen(4)
            meta = os.stat(name, dir_fd=self._dirfd, follow_symlinks=False)
            if not stat.S_ISSOCK(meta.st_mode) or meta.st_uid != os.geteuid():
                raise ValueError("snapshot unavailable")
            self._identity = (meta.st_dev, meta.st_ino)
            self.listener = BoundedUnixListener(self.socket)
        except BaseException:
            if self.socket is not None:
                self.socket.close()
            if self._dirfd is not None:
                os.close(self._dirfd)
                self._dirfd = None
            raise

    def close(self):
        if self._dirfd is None:
            return
        try:
            self.listener.close()
            # Linux provides no atomic unlink-if-inode-matches operation.
            # Preserve mode deliberately leaves the endpoint for an
            # independently trusted owner to reclaim after shutdown.
            if self._cleanup_policy == "preserve":
                return
            parent = self._directory.lstat()
            pinned = os.fstat(self._dirfd)
            if (not stat.S_ISDIR(parent.st_mode)
                    or (parent.st_dev, parent.st_ino) != self._directory_identity
                    or (pinned.st_dev, pinned.st_ino) != self._directory_identity
                    or pinned.st_uid != os.geteuid()
                    or stat.S_IMODE(pinned.st_mode) != 0o700):
                return
            try:
                meta = os.stat(self._name, dir_fd=self._dirfd, follow_symlinks=False)
            except FileNotFoundError:
                return
            if (self._identity == (meta.st_dev, meta.st_ino)
                    and stat.S_ISSOCK(meta.st_mode)):
                os.unlink(self._name, dir_fd=self._dirfd)
        except FileNotFoundError:
            return
        finally:
            os.close(self._dirfd)
            self._dirfd = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
