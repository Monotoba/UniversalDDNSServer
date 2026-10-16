"""Socket activation contract and authenticated ping handler smoke checks."""
import os
import socket
import stat
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from universalddns.operator_broker_service import (
    inherited_listener, serve, validate_endpoint_filesystem, validate_endpoint_ownership,
)


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


    def test_sibling_socket_inside_runtime_directory_refused(self):
        self._assert_unexpected_endpoint("/run/universalddns/other.sock")

    def test_nested_socket_inside_runtime_directory_refused(self):
        self._assert_unexpected_endpoint("/run/universalddns/nested/operator.sock")

    def test_parent_directory_prefix_trick_refused(self):
        self._assert_unexpected_endpoint("/run/universalddns-evil/operator.sock")

    def _assert_unexpected_endpoint(self, endpoint):
        """Exercise full activation checks without altering process fd 3."""
        candidate = MagicMock()
        candidate.family = socket.AF_UNIX
        candidate.type = socket.SOCK_STREAM
        candidate.getsockopt.return_value = 1
        candidate.getsockname.return_value = endpoint
        with patch.dict(os.environ, {"LISTEN_PID": str(os.getpid()),
                                     "LISTEN_FDS": "1"}, clear=True):
            with patch("universalddns.operator_broker_service.os.fstat",
                       return_value=os.stat_result((0o140000, 0, 0, 0, 0, 0, 0, 0, 0, 0))), \
                 patch("universalddns.operator_broker_service.socket.fromfd",
                       return_value=candidate):
                with self.assertRaisesRegex(RuntimeError, "unexpected Unix socket path"):
                    inherited_listener()
        candidate.close.assert_called_once_with()




class BrokerFilesystemTests(unittest.TestCase):
    """Fail closed on an untrusted runtime directory or socket endpoint."""

    @staticmethod
    def fake_stat(mode, uid=0):
        return os.stat_result((mode, 0, 0, 0, uid, 0, 0, 0, 0, 0))

    def verify(self, parent, endpoint, expected=None):
        with patch("universalddns.operator_broker_service.os.lstat",
                   side_effect=[parent, endpoint]) as lstat:
            if expected:
                with self.assertRaisesRegex(RuntimeError, expected):
                    validate_endpoint_filesystem()
            else:
                validate_endpoint_filesystem()
        self.assertEqual(lstat.call_args_list[0].args[0], "/run/universalddns")
        if lstat.call_count == 2:
            self.assertEqual(lstat.call_args_list[1].args[0],
                             "/run/universalddns/operator.sock")

    def test_expected_root_directory_and_group_socket(self):
        self.verify(self.fake_stat(stat.S_IFDIR | 0o711),
                    self.fake_stat(stat.S_IFSOCK | 0o660))

    def test_root_owned_directory_without_operator_traversal_denied(self):
        self.verify(self.fake_stat(stat.S_IFDIR | 0o750),
                    None, "not traversable")

    def test_non_root_parent_denied(self):
        self.verify(self.fake_stat(stat.S_IFDIR | 0o750, uid=1000),
                    None, "root-owned")

    def test_world_writable_parent_denied(self):
        self.verify(self.fake_stat(stat.S_IFDIR | 0o777),
                    None, "group/other writable")

    def test_group_writable_parent_denied(self):
        self.verify(self.fake_stat(stat.S_IFDIR | 0o770),
                    None, "group/other writable")

    def test_parent_symlink_denied(self):
        self.verify(self.fake_stat(stat.S_IFLNK | 0o777),
                    None, "root-owned directory")

    def test_endpoint_symlink_denied(self):
        self.verify(self.fake_stat(stat.S_IFDIR | 0o711),
                    self.fake_stat(stat.S_IFLNK | 0o777), "filesystem socket")

    def test_world_accessible_socket_denied(self):
        self.verify(self.fake_stat(stat.S_IFDIR | 0o711),
                    self.fake_stat(stat.S_IFSOCK | 0o666), "too broad")

    def test_missing_endpoint_denied(self):
        with patch("universalddns.operator_broker_service.os.lstat",
                   side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError):
                validate_endpoint_filesystem()


class BrokerOwnershipTests(unittest.TestCase):
    @staticmethod
    def check(uid=100, gid=200, mode=0o660, error=None):
        record = os.stat_result((stat.S_IFSOCK | mode, 0, 0, 0,
                                 uid, gid, 0, 0, 0, 0))
        with patch("universalddns.operator_broker_service.pwd.getpwnam",
                   return_value=type("User", (), {"pw_uid": 100})()), \
             patch("universalddns.operator_broker_service.grp.getgrnam",
                   return_value=type("Group", (), {"gr_gid": 200})()), \
             patch("universalddns.operator_broker_service.os.lstat",
                   return_value=record):
            if error is None:
                validate_endpoint_ownership()
            else:
                with unittest.TestCase().assertRaisesRegex(RuntimeError, error):
                    validate_endpoint_ownership()

    def test_expected_ownership(self):
        self.check()

    def test_wrong_owner_refused(self):
        self.check(uid=101, error="ownership")

    def test_wrong_group_refused(self):
        self.check(gid=201, error="ownership")

    def test_wrong_mode_refused(self):
        self.check(mode=0o666, error="mode")

    def test_missing_service_account_refused(self):
        with patch("universalddns.operator_broker_service.pwd.getpwnam",
                   side_effect=KeyError):
            with self.assertRaisesRegex(RuntimeError, "account or group unavailable"):
                validate_endpoint_ownership()


class BrokerLifecycleTests(unittest.TestCase):
    def test_listener_processes_client_and_stops_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/operator.sock"
            stop = threading.Event()
            handled = threading.Event()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(path)
                listener.listen(2)
                def process(connection):
                    self.assertEqual(connection.recv(4), b"ping")
                    handled.set()

                with patch("universalddns.operator_broker_service.handle_connection",
                           side_effect=process):
                    thread = threading.Thread(target=serve, args=(listener, stop),
                                              daemon=True)
                    thread.start()
                    try:
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                            client.connect(path)
                            client.sendall(b"ping")
                        self.assertTrue(handled.wait(2), "listener did not process client")
                    finally:
                        stop.set()
                        thread.join(timeout=2)
                    self.assertFalse(thread.is_alive(), "listener did not stop")

    def test_idle_listener_stops_without_incoming_clients(self):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/operator.sock"
            stop = threading.Event()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(path)
                listener.listen(1)
                thread = threading.Thread(target=serve, args=(listener, stop), daemon=True)
                thread.start()
                stop.set()
                thread.join(timeout=2)
                self.assertFalse(thread.is_alive())

if __name__ == "__main__":
    unittest.main()
