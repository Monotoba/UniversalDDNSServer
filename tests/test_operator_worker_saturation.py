"""Bounded-worker admission and release regression tests; no systemd interaction."""
from contextlib import ExitStack
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from universalddns.operator_broker_service import MAX_ACTIVE_CONNECTIONS, serve


class BrokerWorkerAdmissionTests(unittest.TestCase):
    def test_saturation_limits_handlers_and_recovers_after_exceptions(self):
        self.assertEqual(MAX_ACTIVE_CONNECTIONS, 4)
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/broker.sock"
            stop = threading.Event()
            release = threading.Event()
            four_running = threading.Event()
            state_lock = threading.Lock()
            state = {"current": 0, "maximum": 0, "entered": 0}
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(path)
                listener.listen(8)

                def handler(connection):
                    data = connection.recv(32)
                    with state_lock:
                        state["current"] += 1
                        state["entered"] += 1
                        state["maximum"] = max(state["maximum"], state["current"])
                        if state["entered"] == 4:
                            four_running.set()
                    try:
                        if data == b"hold":
                            if not release.wait(3):
                                raise AssertionError("hold workers never released")
                            # Exercise worker exception/slot release path.
                            raise ValueError("injected handler failure")
                        if data == b"ping":
                            connection.sendall(b"pong")
                    finally:
                        with state_lock:
                            state["current"] -= 1

                with patch("universalddns.operator_broker_service.handle_connection",
                           side_effect=handler):
                    thread = threading.Thread(target=serve, args=(listener, stop),
                                              daemon=True)
                    thread.start()
                    with ExitStack() as stack:
                        try:
                            for _ in range(4):
                                client = stack.enter_context(socket.socket(socket.AF_UNIX))
                                client.settimeout(4)
                                client.connect(path)
                                client.sendall(b"hold")
                            self.assertTrue(four_running.wait(2), "four workers not running")
                            extra = stack.enter_context(socket.socket(socket.AF_UNIX))
                            extra.settimeout(4)
                            extra.connect(path)
                            extra.sendall(b"ping")
                            # A full pool must not dispatch the fifth client.
                            with state_lock:
                                self.assertEqual(state["entered"], 4)
                                self.assertEqual(state["maximum"], 4)
                            release.set()
                            self.assertEqual(extra.recv(4), b"pong")
                            with state_lock:
                                self.assertEqual(state["maximum"], 4)
                                self.assertEqual(state["entered"], 5)
                        finally:
                            release.set()
                            stop.set()
                            thread.join(timeout=4)
                    self.assertFalse(thread.is_alive(), "listener failed to stop")

    def test_exception_releases_all_slots_for_followup_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            path = directory + "/broker.sock"
            stop = threading.Event()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(path)
                listener.listen(8)
                def handler(connection):
                    data = connection.recv(32)
                    if data == b"fail":
                        raise OSError("injected read failure")
                    connection.sendall(b"pong")
                with patch("universalddns.operator_broker_service.handle_connection",
                           side_effect=handler):
                    thread = threading.Thread(target=serve, args=(listener, stop),
                                              daemon=True)
                    thread.start()
                    try:
                        for _ in range(8):
                            with socket.socket(socket.AF_UNIX) as c:
                                c.settimeout(3)
                                c.connect(path)
                                c.sendall(b"fail")
                                self.assertEqual(c.recv(1), b"")
                        with socket.socket(socket.AF_UNIX) as c:
                            c.settimeout(3)
                            c.connect(path)
                            c.sendall(b"ping")
                            self.assertEqual(c.recv(4), b"pong")
                    finally:
                        stop.set()
                        thread.join(timeout=3)
                    self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
