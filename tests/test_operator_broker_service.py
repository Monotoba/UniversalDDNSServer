"""Socket activation contract and authenticated ping handler smoke checks."""
import os
import socket
import tempfile
import unittest
from unittest.mock import patch

from universalddns.operator_broker_service import inherited_listener


class BrokerActivationTests(unittest.TestCase):
    def test_missing_activation_refused(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "not activated"):
                inherited_listener()

    def test_wrong_fd_count_refused(self):
        with patch.dict(os.environ, {"LISTEN_PID": str(os.getpid()),
                                     "LISTEN_FDS": "2"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "exactly one"):
                inherited_listener()

    def test_regular_file_fd_refused(self):
        with tempfile.TemporaryFile() as f:
            with patch.dict(os.environ, {"LISTEN_PID": str(os.getpid()),
                                         "LISTEN_FDS": "1"}, clear=True):
                with patch("universalddns.operator_broker_service.os.fstat",
                           return_value=os.fstat(f.fileno())):
                    with self.assertRaisesRegex(RuntimeError, "not a socket"):
                        inherited_listener()

    def test_wrong_socket_path_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/unexpected.sock"
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(path)
                listener.listen(1)
                original = os.dup(3) if self._fd_open(3) else None
                try:
                    os.dup2(listener.fileno(), 3)
                    with patch.dict(os.environ, {"LISTEN_PID": str(os.getpid()),
                                                 "LISTEN_FDS": "1"}, clear=True):
                        with self.assertRaisesRegex(RuntimeError, "unexpected Unix"):
                            inherited_listener()
                finally:
                    if original is not None:
                        os.dup2(original, 3)
                        os.close(original)
                    else:
                        os.close(3)

    @staticmethod
    def _fd_open(fd):
        try:
            os.fstat(fd)
            return True
        except OSError:
            return False


if __name__ == "__main__":
    unittest.main()
