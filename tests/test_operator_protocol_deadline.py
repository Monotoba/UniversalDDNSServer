"""Total request deadline cannot be extended by clients drip-feeding bytes."""
import unittest
from unittest.mock import Mock, patch

from universalddns.operator_protocol import read_request


class TotalRequestDeadlineTests(unittest.TestCase):
    def test_drip_feed_is_refused_after_total_budget(self):
        connection = Mock()
        connection.recv.side_effect = [b"x", b"x"]
        with patch("universalddns.operator_protocol.time.monotonic",
                   side_effect=[10.0, 10.0, 10.75, 12.1]):
            with self.assertRaisesRegex(TimeoutError, "deadline exceeded"):
                read_request(connection)
        self.assertEqual(connection.recv.call_count, 2)
        self.assertEqual([round(c.args[0], 2) for c in
                          connection.settimeout.call_args_list], [2.0, 1.25])

    def test_budget_exhausted_before_first_recv(self):
        connection = Mock()
        with patch("universalddns.operator_protocol.time.monotonic",
                   side_effect=[10.0, 12.0]):
            with self.assertRaisesRegex(TimeoutError, "deadline exceeded"):
                read_request(connection)
        connection.recv.assert_not_called()


if __name__ == "__main__":
    unittest.main()
