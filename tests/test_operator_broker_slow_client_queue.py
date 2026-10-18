"""End-to-end bounded sequential listener behavior with a stalled client."""
import json
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from universalddns.operator_broker_service import serve


class BrokerSlowClientQueueTests(unittest.TestCase):
    def test_second_client_is_served_after_first_client_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/operator.sock"
            stop = threading.Event()
            failures = []
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(path)
                listener.listen(4)

                def runner():
                    try:
                        serve(listener, stop)
                    except Exception as exc:
                        failures.append(exc)

                with patch("universalddns.operator_broker.authenticated_operator_peer",
                           return_value="fixture-operator"):
                    thread = threading.Thread(target=runner, daemon=True)
                    thread.start()
                    try:
                        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as slow:
                            slow.settimeout(6)
                            slow.connect(path)
                            slow.sendall(b'{"version":1')
                            # Wait until the broker has accepted the slow request,
                            # then queue an entire second ping.
                            time.sleep(0.15)
                            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as fast:
                                fast.settimeout(6)
                                fast.connect(path)
                                start = time.monotonic()
                                fast.sendall(b'{"version":1,"operation":"ping"}\n')
                                result = json.loads(fast.recv(1024))
                                elapsed = time.monotonic() - start
                            self.assertEqual(result, {
                                "ok": True, "operator": "fixture-operator", "version": 1
                            })
                            self.assertLess(elapsed, 4.5, "second client blocked too long")
                    finally:
                        stop.set()
                        thread.join(timeout=6)
                    self.assertFalse(thread.is_alive(), "listener did not stop")
                    self.assertFalse(failures, failures)


if __name__ == "__main__":
    unittest.main()
