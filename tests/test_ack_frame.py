"""Bounded binary acknowledgement format adversarial tests."""
import unittest

from universalddns.ack_frame import FRAME_BYTES, decode_ack, encode_ack


class AcknowledgementFrameTests(unittest.TestCase):
    def test_round_trip(self):
        nonce = "12" * 32
        generation = "ab" * 16
        frame = encode_ack(nonce, generation)
        self.assertEqual(len(frame), FRAME_BYTES)
        self.assertEqual(decode_ack(frame, nonce), generation)

    def test_truncated_oversize_corrupted_and_wrong_nonce(self):
        nonce = "12" * 32
        frame = encode_ack(nonce, "ab" * 16)
        for payload, expected in (
            (frame[:-1], nonce),
            (frame + b"x", nonce),
            (b"BAD!" + frame[4:], nonce),
            (frame, "ff" * 32),
            (frame, "broken"),
            (bytearray(frame), nonce),
        ):
            with self.subTest(payload=payload, expected=expected):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    decode_ack(payload, expected)

    def test_rejects_invalid_encoder_inputs(self):
        for nonce, generation in (
            ("bad", "ab" * 16),
            ("ab" * 32, "bad"),
            ("gg" * 32, "ab" * 16),
            (None, "ab" * 16),
        ):
            with self.subTest(nonce=nonce, generation=generation):
                with self.assertRaisesRegex(ValueError, "^snapshot unavailable$"):
                    encode_ack(nonce, generation)


if __name__ == "__main__":
    unittest.main()
