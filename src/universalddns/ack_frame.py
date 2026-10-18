"""Fixed-size binary acknowledgement frame for the isolated child observer.

The multiprocessing Connection supplies length framing; recv_bytes(maxlength)
rejects oversized bodies before allocating/decoding Python objects.
"""
import uuid

MAGIC = b"UACK"
FRAME_BYTES = 52


def encode_ack(nonce: str, generation: str) -> bytes:
    try:
        if (type(nonce) is not str or len(nonce) != 64
                or type(generation) is not str or len(generation) != 32):
            raise ValueError("snapshot unavailable")
        frame = MAGIC + bytes.fromhex(nonce) + uuid.UUID(hex=generation).bytes
        if len(frame) != FRAME_BYTES:
            raise ValueError("snapshot unavailable")
        return frame
    except (TypeError, ValueError) as exc:
        raise ValueError("snapshot unavailable") from exc


def decode_ack(frame: bytes, expected_nonce: str) -> str:
    try:
        if type(frame) is not bytes or len(frame) != FRAME_BYTES:
            raise ValueError("snapshot unavailable")
        if frame[:4] != MAGIC or frame[4:36] != bytes.fromhex(expected_nonce):
            raise ValueError("snapshot unavailable")
        if type(expected_nonce) is not str or len(expected_nonce) != 64:
            raise ValueError("snapshot unavailable")
        return uuid.UUID(bytes=frame[36:52]).hex
    except (TypeError, ValueError) as exc:
        raise ValueError("snapshot unavailable") from exc
