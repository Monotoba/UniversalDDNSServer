"""Exercise the real inherited fd 3 contract in a forked Linux process.

No privileged user, real systemd instance, or fixed runtime path is needed.
This is a negative activation test, not a deployed systemd integration test.
"""
import os
import socket
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform.startswith("linux") and hasattr(os, "fork"),
                     "Linux fork and AF_UNIX required")
class InheritedFDIntegrationTests(unittest.TestCase):
    def test_real_fd_three_refuses_unexpected_bound_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "operator.sock")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(path)
                listener.listen(1)
                read_fd, write_fd = os.pipe()
                try:
                    child_pid = os.fork()
                    if child_pid == 0:
                        try:
                            os.close(read_fd)
                            os.dup2(listener.fileno(), 3)
                            os.environ["LISTEN_PID"] = str(os.getpid())
                            os.environ["LISTEN_FDS"] = "1"
                            os.environ["LISTEN_FDNAMES"] = "operator"
                            from universalddns.operator_broker_service import inherited_listener
                            try:
                                with inherited_listener():
                                    result = b"unexpectedly accepted"
                            except RuntimeError as exc:
                                result = (b"ok" if "unexpected Unix socket path" in str(exc)
                                          else b"wrong error")
                            os.write(write_fd, result)
                        except BaseException:
                            os.write(write_fd, b"child error")
                        finally:
                            os._exit(0)
                    os.close(write_fd)
                    write_fd = -1
                    result = os.read(read_fd, 128)
                    _, status = os.waitpid(child_pid, 0)
                    self.assertTrue(os.WIFEXITED(status))
                    self.assertEqual(result, b"ok")
                finally:
                    os.close(read_fd)
                    if write_fd != -1:
                        os.close(write_fd)


if __name__ == "__main__":
    unittest.main()
