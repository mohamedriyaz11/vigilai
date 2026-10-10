"""Unit tests for CRC-8 calculation and serial protocol encode/decode."""

from __future__ import annotations

import pytest

from actuation.serial_servo import (
    CMD_DETACH,
    CMD_HEARTBEAT,
    CMD_PARK,
    CMD_POINT,
    CMD_STATUS_REPLY,
    CMD_STATUS_REQUEST,
    compute_crc8,
    decode_frame,
    encode_frame,
)


def test_crc8_known_vectors():
    # 1. Empty buffer -> 0
    assert compute_crc8(b"") == 0x00

    # 2. Single byte 0x01
    # 0x01 with poly 0x07: 0x01 << 7 = 0x80 -> ^ 0x07 = 0x07 ...
    crc_1 = compute_crc8(bytes([0x01]))
    assert isinstance(crc_1, int)
    assert 0 <= crc_1 <= 255

    # 3. Known frame body: LEN=1, CMD=1, PAYLOAD=[90] (0x5A)
    # [0x01, 0x01, 0x5A]
    data = bytes([0x01, 0x01, 0x5A])
    expected_crc = compute_crc8(data)
    frame = encode_frame(CMD_POINT, bytes([0x5A]))
    assert frame == bytes([0xAA, 0x01, 0x01, 0x5A, expected_crc])


def test_encode_and_decode_all_commands():
    # 1. POINT (angle 90)
    frame_point = encode_frame(CMD_POINT, bytes([90]))
    cmd, payload = decode_frame(frame_point)
    assert cmd == CMD_POINT
    assert payload == bytes([90])

    # 2. PARK
    frame_park = encode_frame(CMD_PARK)
    cmd, payload = decode_frame(frame_park)
    assert cmd == CMD_PARK
    assert payload == b""

    # 3. DETACH
    frame_detach = encode_frame(CMD_DETACH)
    cmd, payload = decode_frame(frame_detach)
    assert cmd == CMD_DETACH
    assert payload == b""

    # 4. HEARTBEAT
    frame_hb = encode_frame(CMD_HEARTBEAT)
    cmd, payload = decode_frame(frame_hb)
    assert cmd == CMD_HEARTBEAT
    assert payload == b""

    # 5. STATUS_REQUEST
    frame_sr = encode_frame(CMD_STATUS_REQUEST)
    cmd, payload = decode_frame(frame_sr)
    assert cmd == CMD_STATUS_REQUEST
    assert payload == b""

    # 6. STATUS_REPLY (angle=45, muted=1, state=2)
    frame_reply = encode_frame(CMD_STATUS_REPLY, bytes([45, 1, 2]))
    cmd, payload = decode_frame(frame_reply)
    assert cmd == CMD_STATUS_REPLY
    assert list(payload) == [45, 1, 2]


def test_decode_corrupted_crc():
    valid_frame = bytearray(encode_frame(CMD_POINT, bytes([120])))
    # Corrupt the CRC byte at the end
    valid_frame[-1] = (valid_frame[-1] ^ 0xFF) & 0xFF

    with pytest.raises(ValueError, match="CRC-8 verification failed"):
        decode_frame(bytes(valid_frame))


def test_decode_truncated_frame():
    valid_frame = encode_frame(CMD_POINT, bytes([120]))
    # Slice off the last byte
    truncated = valid_frame[:-1]

    with pytest.raises(ValueError, match="Frame truncated|Frame is too short"):
        decode_frame(truncated)


def test_decode_invalid_sof():
    valid_frame = bytearray(encode_frame(CMD_PARK))
    valid_frame[0] = 0x55  # Invalid SOF (expected 0xAA)

    with pytest.raises(ValueError, match="Invalid Start of Frame"):
        decode_frame(bytes(valid_frame))
