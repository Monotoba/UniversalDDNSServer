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
                with patch.dict(os.environ, {"LISTEN_PID": str(os.getpid()),
                                             "LISTEN_FDS": "1"}, clear=True):
                    with patch("universalddns.operator_broker_service.os.fstat",
                               return_value=os.fstat(listener.fileno())), \
                         patch("universalddns.operator_broker_service.socket.fromfd",
                               return_value=listener.dup()):
                        with self.assertRaisesRegex(RuntimeError, "unexpected Unix"):
                            inherited_listener()


    def test_other_socket_inside_runtime_directory_refused(self):
        """A sibling name must not be accepted merely for sharing a prefix."""
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/other.sock"
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(path)
                listener.listen(1)
                with patch.dict(os.environ, {"LISTEN_PID": str(os.getpid()),
                                             "LISTEN_FDS": "1"}, clear=True):
                    with patch("universalddns.operator_broker_service.os.fstat",
                               return_value=os.fstat(listener.fileno())), \
                         patch("universalddns.operator_broker_service.socket.fromfd",
                               return_value=listener.dup()):
                        # Pretend the listener is under the configured parent,
                        # but give it the wrong basename.
                        with patch.object(socket.socket, "getsockname",
                                          return_value="/run/universalddns/other.sock"):
                            with self.assertRaisesRegex(RuntimeError, "unexpected Unix socket path"):
                                inherited_listener()

    def test_nested_socket_inside_runtime_directory_refused(self):
        """A nested path is not the configured socket endpoint."""
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/other.sock"
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(path)
                listener.listen(1)
                with patch.dict(os.environ, {"LISTEN_PID": str(os.getpid()),
                                             "LISTEN_FDS": "1"}, clear=True):
                    with patch("universalddns.operator_broker_service.os.fstat",
                               return_value=os.fstat(listener.fileno())), \
                         patch("universalddns.operator_broker_service.socket.fromfd",
                               return_value=listener.dup()):
                        with patch.object(socket.socket, "getsockname",
                                          return_value="/run/universalddns/nested/operator.sock"):
                            with self.assertRaisesRegex(RuntimeError, "unexpected Unix socket path"):
                                inherited_listener()


if __name__ == "__main__":
    unittest.main()
