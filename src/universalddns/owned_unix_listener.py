"""Disposable Unix socket pathname lifecycle.

Only a socket in an already-private directory is eligible. Never unlink
an unknown existing pathname; shutdown removes only the original inode.
"""
import os
import socket
import stat
from pathlib import Path

from .bounded_unix_listener import BoundedUnixListener


class OwnedUnixListener:
    def __init__(self, parent: str | Path, name: str = "ipc.sock"):
        directory = Path(parent)
        if (name != "ipc.sock" or directory.is_symlink()
                or not directory.is_dir()):
            raise ValueError("snapshot unavailable")
        directory_stat = directory.stat()
        if (directory_stat.st_uid != os.geteuid()
                or stat.S_IMODE(directory_stat.st_mode) != 0o700):
            raise ValueError("snapshot unavailable")
        self._directory = directory
        self._directory_identity = (directory_stat.st_dev, directory_stat.st_ino)
        self.path = directory / name
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._identity = None
        try:
            self.socket.bind(str(self.path))
            self.socket.listen(4)
            meta = self.path.lstat()
            if not stat.S_ISSOCK(meta.st_mode) or meta.st_uid != os.geteuid():
                raise ValueError("snapshot unavailable")
            self._identity = (meta.st_dev, meta.st_ino)
            self.listener = BoundedUnixListener(self.socket)
        except BaseException:
            self.socket.close()
            raise

    def close(self):
        self.listener.close()
        try:
            parent = self._directory.lstat()
            if (not stat.S_ISDIR(parent.st_mode)
                    or (parent.st_dev, parent.st_ino) != self._directory_identity
                    or parent.st_uid != os.geteuid()
                    or stat.S_IMODE(parent.st_mode) != 0o700):
                return
            meta = self.path.lstat()
        except FileNotFoundError:
            return
        if (self._identity == (meta.st_dev, meta.st_ino)
                and stat.S_ISSOCK(meta.st_mode)):
            self.path.unlink()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
